# Painel Patrimonial

App pessoal de renda fixa (FGC e Tesouro Nacional): reserva de emergência com proteção FGC, comparador de 23 produtos com três cenários de juros, catálogo de LCI, LCA, CRI, CRA, debêntures e Tesouro, metas, renda passiva e carteira.

**Endereço:** https://paulohtai.github.io/painel-patrimonial/

## Como os dados se atualizam

- `.github/workflows/atualizar-mercado.yml` roda em dias úteis às 8h30 e 19h30 (Brasília).
- `scripts/atualizar_mercado.py` busca Selic, CDI, IPCA e TR no Banco Central (SGS), medianas do Focus e as taxas do Tesouro Direto no Tesouro Transparente, e grava `data/mercado.json`.
- Cada fonte é independente: se uma falhar, o valor anterior é mantido e o campo `status` registra a falha.
- `data/ofertas.json` guarda o catálogo de títulos (LCI, LCA, CRI, CRA, debêntures, LF e Tesouro) e é revisado toda semana.
- Taxas de CDBs e caixinhas de bancos não têm fonte oficial pública; ficam no `index.html` com fonte e data, e o app avisa quando passam de 30 dias.

## Privacidade

Carteira, reserva e ajustes ficam só no aparelho (localStorage). Nada pessoal vai para este repositório. Use a tela Carteira para fazer backup.
