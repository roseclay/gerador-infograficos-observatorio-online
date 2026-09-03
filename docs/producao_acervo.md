# Produção recorrente com acervo versionado

Este documento descreve a camada nova de acervo do gerador de infográficos. Ela foi criada para preservar o editor de imagem-base já aprovado e acrescentar persistência, versionamento de CSVs, catálogo de indicadores e gráficos editáveis.

## O que fica persistido

- Conjuntos de dados, com ID estável, fonte pública, responsável, histórico de versões e versão ativa.
- Versões de CSV, com checksum, esquema detectado, período/cobertura, validação e caminho imutável.
- Imagens-base, separando base limpa de produção e referência preenchida.
- Versões de imagens-base, com checksum, dimensões, status de revisão e arquivo imutável.
- Definições de indicadores, sem valores embutidos.
- Infográficos, revisões de layout, elementos posicionados, vínculos de dados e versões aplicadas.
- Registros de geração, com revisão exata, arquivos gerados e validação.

No ambiente local, esses metadados e arquivos ficam em `storage/acervo/`, que é ignorado pelo Git. Esse modo serve para desenvolvimento, testes e uso local. Ele deve aparecer como local, não como sincronizado.

## Fluxo recomendado

1. Abra o modo `Imagem-base (padrão)`.
2. Na tela inicial, entre em `Dados`.
3. Cadastre um conjunto e envie o CSV v1.
4. Entre em `Imagens-base`.
5. Cadastre a base limpa de produção.
6. Abra `Infográficos` e clique em `Novo infográfico`.
7. No painel `Acervo`, use a base cadastrada e selecione o conjunto de dados.
8. Clique em `Adicionar campos vinculados`.
9. Arraste os campos da tabela para a arte.
10. Para gráficos, use `Adicionar gráfico vinculado`, escolha indicadores e insira barras horizontais ou colunas verticais.
11. Salve com `Salvar no acervo`.
12. Gere a imagem final.

## Atualizar dados sem reconstruir o layout

1. Volte para `Dados`.
2. Cadastre nova versão do mesmo conjunto, não um conjunto novo.
3. O sistema registra checksum, revisão e validação.
4. Infográficos que usam esse conjunto passam a aparecer com atualização disponível.
5. Clique em `Atualizar vínculos do acervo` no editor ou `Atualizar todos` na tela inicial.
6. Os valores e as séries dos gráficos são recalculados.
7. Posições, dimensões, estilos, textos manuais, base e ordem dos elementos são preservados.

Ausência de campo obrigatório, duplicata de chave lógica, valor incompatível ou vínculo ambíguo bloqueia a atualização daquele infográfico. A versão anterior continua válida.

## Formato longo recomendado

```csv
indicador_id,periodo,recorte_id,valor
pesquisadores_ativos,2021-2026,bahia_total,11493
grupos_pesquisa,2021-2026,bahia_total,1429
```

Dimensões adicionais podem ser incluídas quando tiverem significado declarado, por exemplo `instituicao`, `categoria`, `ano`, `genero` ou `territorio`. A chave lógica da observação deve incluir indicador e todas as dimensões relevantes.

## CSVs legados

O modo anterior continua aceitando CSV agregado simples e CSV detalhado. Para CSVs sem `indicador_id`, o catálogo sugere vínculos por aliases, mas isso não resolve ambiguidades sozinho. Um vínculo legado sem identidade confiável deve ser revisado antes de virar fluxo recorrente.

## Gráficos editáveis

Os gráficos são elementos do canvas, assim como textos. Eles têm:

- ID próprio;
- vínculo com conjunto, versão e indicadores;
- posição, largura, altura e ordem;
- orientação horizontal ou vertical;
- séries com valores brutos e exibidos;
- escala compartilhada por série.

Não use `st.bar_chart` para produção visual do infográfico. A composição final é renderizada pelo mesmo mecanismo usado na exportação.

## Backup e restauração

Na aba `Backup`, gere um ZIP local. Ele inclui:

- `archive.json`;
- CSVs versionados;
- imagens-base versionadas.

Para produção com Supabase, faça backup do PostgreSQL e também do bucket Storage. Um backup apenas do banco não inclui os arquivos binários.

## Configuração Supabase

A migração versionada fica em:

```text
supabase/migrations/202609020001_acervo_infograficos.sql
```

Ela cria as tabelas, índices, RLS básico para usuários autenticados e bucket privado `observatorio-infograficos`.

Configure segredos fora do Git:

```toml
[archive]
provider = "supabase"

[access]
password = "SENHA_DA_EQUIPE"

[supabase]
url = "https://SEU-PROJETO.supabase.co"
anon_key = "SUPABASE_ANON_KEY"
bucket = "observatorio-infograficos"
service_role_key = "SUPABASE_SERVICE_ROLE_KEY"
```

Use `.streamlit/secrets.toml.example` como modelo. Não commite `.streamlit/secrets.toml`.

Com esses segredos, o aplicativo passa a abrir o acervo remoto automaticamente. A equipe vê uma tela simples de senha da própria ferramenta; depois usa as abas normais de `Dados`, `Imagens-base`, `Catálogo`, `Infográficos` e `Backup`.

## Compartilhamento com a equipe

Quem administra precisa fazer uma única configuração:

1. Criar ou abrir o projeto Supabase do Observatório.
2. Aplicar a migração SQL em `supabase/migrations/202609020001_acervo_infograficos.sql`.
3. Conferir se o bucket privado `observatorio-infograficos` foi criado.
4. Copiar `Project URL`, `anon public key` e `service_role key` no painel do Supabase.
5. Adicionar no Streamlit Community Cloud os secrets `archive.provider`, `access.password`, `supabase.url`, `supabase.anon_key`, `supabase.service_role_key` e `supabase.bucket`.
6. Reiniciar o aplicativo.

Depois disso, a equipe não precisa mexer no Supabase. O fluxo normal é pelo Streamlit:

1. A pessoa abre o link público ou restrito do app.
2. Digita a senha da equipe.
3. Envia CSVs pela aba `Dados`.
4. Envia uma ou várias artes limpas pela aba `Imagens-base`.
5. Salva e reabre infográficos pelo `Acervo persistente`.
6. Publica nova versão do CSV no mesmo conjunto para liberar o botão de atualização dos infográficos vinculados.

Na aba `Imagens-base`, marque corretamente o tipo:

- `Base limpa de produção`: fundo usado pelo gerador. Não deve conter números, percentuais, barras de gráfico, datas ou textos que mudarão.
- `Referência preenchida`: imagem já montada, usada apenas como exemplo visual. Ela pode orientar posicionamento e aparência, mas não deve ser fundo final de produção.

Se o time preferir contas individuais, remova `supabase.service_role_key` dos secrets e crie usuários em Authentication no Supabase. Nesse modo, cada pessoa entra com e-mail e senha do Supabase diretamente no app. Para a operação cotidiana, o modelo simples com `access.password` é mais fácil.

Nunca coloque `supabase.service_role_key` em arquivo versionado, YAML, print ou mensagem pública.

## Limitações atuais

- A persistência local é real, mas não é adequada como armazenamento permanente no Streamlit Community Cloud.
- A integração Supabase está implementada no código e pronta para ativação por secrets; sem credenciais reais, não é possível validar operações contra o serviço remoto neste ambiente.
- As referências `info01.png` a `info05.png` são imagens preenchidas, não bases limpas de produção.
- O catálogo inicial traz conceitos e aliases, não critérios oficiais completos. Definições pendentes exigem validação semântica da equipe.
- Gráficos de barras horizontais e colunas verticais estão implementados; outros tipos devem ser adicionados como novos elementos.

## Limites gratuitos consultados em 02/09/2026

No plano Free do Supabase, a página oficial indicava:

- banco de dados de 500 MB por projeto;
- Storage de 1 GB;
- 5 GB de egress;
- upload máximo de arquivo de 50 MB;
- pausa após 1 semana de inatividade;
- limite de 2 projetos ativos.

Esses limites podem mudar. Confirme novamente antes de usar o acervo remoto para produção institucional.

## Reversão

Como a camada nova é aditiva, a reversão operacional é abrir o modo imagem-base local ou um YAML antigo e não usar o acervo. Para reversão de banco remoto, restaure o backup do PostgreSQL e do Storage correspondente à data anterior.
