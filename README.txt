# Lançamento de Editais — Residência Médica

Este repositório coleta automaticamente posts de editais no portal do Estratégia MED e gera um JSON público para consulta.

## O que é gerado

- `data/editais_min.json` (fonte)
- `site/data/editais_min.json` (cópia usada pela página)

Formato (por item):

```json
{
  "instituicao": "Hospital X",
  "edital": ["https://.../arquivo.pdf", "https://.../anexo.pdf"],
  "link_oficial": "https://site-oficial-da-instituicao",
  "posted_at": "2026-01-10T12:34:56+00:00",
  "captured_at": "2026-01-27T18:01:02.123456+00:00"
}
