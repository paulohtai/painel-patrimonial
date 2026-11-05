"""Atualiza data/mercado.json com dados oficiais.

Fontes:
- Banco Central, SGS: Selic meta (432), CDI anualizado (4389), IPCA 12 meses (13522), TR (226)
- Banco Central, Focus (Olinda): medianas de IPCA e Selic para o ano corrente
- Tesouro Transparente: taxas de compra do Tesouro Direto

Cada fonte é independente. Se uma falhar, o valor anterior é mantido e o
campo "status" registra a falha. Nenhum valor fora de faixas plausíveis é aceito.
Só usa a biblioteca padrão do Python.
"""
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
AGORA = datetime.now(BRT)
CAMINHO = os.path.join(os.path.dirname(__file__), "..", "data", "mercado.json")
UA = {"User-Agent": "Mozilla/5.0 (painel-patrimonial; atualizacao diaria)", "Accept": "*/*"}

# Calendário oficial do Copom (dia do anúncio da decisão)
COPOM = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-08-05",
         "2026-09-16", "2026-11-04", "2026-12-09", "2027-01-27"]

# Títulos acompanhados: id no painel -> (tipo no arquivo do Tesouro, vencimento)
TITULOS = {
    "tselic": ("Tesouro Selic", "01/03/2031"),
    "pre29": ("Tesouro Prefixado", "01/01/2029"),
    "pre32": ("Tesouro Prefixado", "01/01/2032"),
    "ipca32": ("Tesouro IPCA+", "15/08/2032"),
    "ipca40": ("Tesouro IPCA+", "15/08/2040"),
    "pre37s": ("Tesouro Prefixado com Juros Semestrais", "01/01/2037"),
    "ipca37s": ("Tesouro IPCA+ com Juros Semestrais", "15/05/2037"),
    "ipca45s": ("Tesouro IPCA+ com Juros Semestrais", "15/05/2045"),
}
FAIXAS = {"tselic": (-0.5, 1.0), "pre29": (5, 30), "pre32": (5, 30), "ipca32": (2, 15), "ipca40": (2, 15),
          "pre37s": (5, 30), "ipca37s": (2, 15), "ipca45s": (2, 15)}
CSV_TESOURO = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
               "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")


def baixar(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def num_br(txt):
    return float(str(txt).strip().replace(".", "").replace(",", ".")) if "," in str(txt) else float(txt)


def sgs(serie):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json"
    dado = json.loads(baixar(url, 30))[-1]
    return float(str(dado["valor"]).replace(",", ".")), dado["data"]


def focus(indicador, ano):
    filtro = f"Indicador eq '{indicador}' and DataReferencia eq '{ano}' and baseCalculo eq 0"
    q = urllib.parse.urlencode({"$top": "1", "$filter": filtro, "$orderby": "Data desc",
                                "$format": "json", "$select": "Indicador,Data,DataReferencia,Mediana"},
                               quote_via=urllib.parse.quote)  # OData exige %20, não "+"
    url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?" + q
    linha = json.loads(baixar(url, 30))["value"][0]
    return float(linha["Mediana"]), linha["Data"]


def tesouro():
    bruto = baixar(CSV_TESOURO, 180).decode("latin-1")
    leitor = csv.DictReader(io.StringIO(bruto), delimiter=";")
    melhores = {}
    for linha in leitor:
        tipo = (linha.get("Tipo Titulo") or "").strip()
        venc = (linha.get("Data Vencimento") or "").strip()
        base = (linha.get("Data Base") or "").strip()
        for pid, (t, v) in TITULOS.items():
            if tipo == t and venc == v:
                try:
                    d = datetime.strptime(base, "%d/%m/%Y")
                except ValueError:
                    continue
                if pid not in melhores or d > melhores[pid][0]:
                    melhores[pid] = (d, linha.get("Taxa Compra Manha"))
    saida = {}
    for pid, (d, taxa) in melhores.items():
        if (AGORA.replace(tzinfo=None) - d).days > 10:
            continue  # título fora de oferta ou arquivo desatualizado
        valor = num_br(taxa)
        lo, hi = FAIXAS[pid]
        if lo <= valor <= hi:
            saida[pid] = {"taxa": round(valor, 2), "fonte": "Tesouro Transparente", "data": d.strftime("%Y-%m-%d")}
    return saida


def main():
    with open(CAMINHO, encoding="utf-8") as f:
        dados = json.load(f)
    status = {}

    def tenta(nome, fn):
        try:
            fn()
            status[nome] = "ok"
        except Exception as e:  # noqa: BLE001
            status[nome] = f"falhou: {type(e).__name__}"
            print(f"[{nome}] {e}", file=sys.stderr)

    def _selic():
        v, _ = sgs(432)
        assert 1 <= v <= 30
        dados["selic"] = round(v, 2)

    def _cdi():
        v, _ = sgs(4389)
        assert 1 <= v <= 30
        dados["cdi"] = round(v, 2)

    def _ipca():
        v, d = sgs(13522)
        assert -5 <= v <= 30
        dados["ipca12m"] = round(v, 2)
        mes = datetime.strptime(d, "%d/%m/%Y")
        nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
        dados["ipcaRef"] = f"{nomes[mes.month - 1]}/{str(mes.year)[2:]}"

    def _tr():
        v, _ = sgs(226)
        assert 0 <= v <= 2
        dados["tr"] = round(v, 4)

    def _focus():
        ano = AGORA.year
        ipca, _ = focus("IPCA", ano)
        selic, _ = focus("Selic", ano)
        assert -5 <= ipca <= 30 and 1 <= selic <= 30
        dados["focusIpca"], dados["focusSelic"], dados["focusAno"] = round(ipca, 2), round(selic, 2), ano

    def _tesouro():
        novos = tesouro()
        assert novos, "nenhum título encontrado"
        dados.setdefault("produtos", {}).update(novos)

    for nome, fn in [("selic", _selic), ("cdi", _cdi), ("ipca", _ipca), ("tr", _tr),
                     ("focus", _focus), ("tesouro", _tesouro)]:
        tenta(nome, fn)

    hoje = AGORA.strftime("%Y-%m-%d")
    futuras = [d for d in COPOM if d >= hoje]
    dados["proxCopom"] = datetime.strptime(futuras[0], "%Y-%m-%d").strftime("%d/%m") if futuras else "a confirmar"

    if any(v == "ok" for v in status.values()):
        dados["atualizadoEm"] = AGORA.isoformat(timespec="minutes")
        dados["fonte"] = "Banco Central (SGS e Focus) e Tesouro Transparente"
    dados["status"] = status
    with open(CAMINHO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(status, ensure_ascii=False))
    return 0 if any(v == "ok" for v in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
