# Gerador de infográficos institucionais

Ferramenta local para gerar infográficos a partir de uma imagem-base ou, no modo avançado, a partir de indicadores configurados em CSV. O fluxo padrão é simples: a pessoa carrega uma arte pronta, posiciona campos de texto sobre ela e exporta a imagem final.

## Conceito correto

- O modo padrão usa a imagem enviada como base real da exportação.
- No modo avançado de templates, imagens de referência continuam sendo apenas referência visual.
- O CSV de demonstração contém dados fictícios e serve somente para testar a ferramenta.
- A aplicação inicia vazia e não carrega automaticamente exemplos.
- A geração é determinística: a mesma imagem-base, o mesmo CSV/YAML e as mesmas coordenadas produzem o mesmo resultado.
- O modo padrão com imagem-base, campos arrastáveis e prévias por campo é a versão estável elegível para produção.

## Instalação no Windows

Clique duas vezes em `instalar.bat`.

Ou, pelo PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No terminal comum:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Abrir a ferramenta

Clique duas vezes em `iniciar.bat`.

Ou execute:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

A tela inicial abre no modo `Imagem-base (padrão)`.

## Modo padrão: imagem-base

Use este modo quando o design do infográfico já estiver pronto e faltar apenas preencher textos ou números.

Fluxo:

1. Carregue uma imagem-base em PNG ou JPG.
2. Adicione campos manualmente ou carregue um CSV de campos.
3. Arraste uma linha da tabela de campos para a imagem-base para posicionar o dado.
4. Use o canto azul do campo para redimensionar a área de texto.
5. Com uma caixa selecionada, use as setas do teclado para mover 1 px ou `Shift` + seta para mover 10 px.
6. Remova um texto da arte pelo botão `Remover` na tabela ou pelas teclas `Delete`/`Backspace`.
7. Ajuste `coord. X`, `coord. Y`, largura, altura, tamanho da fonte, cor, negrito e alinhamento quando necessário.
8. Salve o infográfico ou gere a imagem final.

Tela inicial:

- lista infográficos salvos;
- mostra nome, data de atualização e quantidade de campos;
- permite abrir um infográfico para atualizar;
- permite gerar um infográfico individual;
- inclui ações `Atualizar todos` e `Gerar todos`.

Tela de edição:

- campo `Nome do infográfico`;
- carregamento da imagem-base;
- carregamento do CSV de campos;
- botão `Atualizar dados`;
- canvas de posicionamento com drag-and-drop;
- tabela lateral de campos carregados do CSV;
- tabela recolhida de ajustes finos;
- botões para salvar configuração e gerar arquivos finais.

Formato recomendado para o CSV de campos:

```csv
imagem_base,campo,valor,x,y,largura,altura,tamanho_fonte,cor,negrito,alinhamento,mostrar_nome,ordem
base.png,Campo A,123,300,420,280,80,56,#0057B8,true,left,false,1
base.png,Campo B,+80,700,420,280,80,56,#0057B8,true,left,false,2
```

Também é aceito um CSV simples com duas colunas, sem cabeçalho, no formato `campo;valor`. Nesse caso, a ferramenta cria posições iniciais automaticamente para posterior ajuste.

Arquivos exportados pelo modo imagem-base:

- PNG final;
- PDF final;
- cópia da imagem-base usada;
- CSV de campos;
- YAML da configuração;
- relatório de validação.

O CSV/YAML salva o nome da imagem-base e as coordenadas dos campos. Para reproduzir exatamente o mesmo infográfico, mantenha a imagem-base e a configuração gerada.

O preview do editor é renderizado pelo mesmo mecanismo usado na exportação. A camada de caixas serve para selecionar, arrastar e redimensionar; o texto exibido na arte corresponde ao PNG final.

## Modo legado: indicadores por CSV

O fluxo principal da equipe é `Imagem-base (padrão)`. O modo `Indicadores por CSV (avançado)` continua preservado apenas como legado, dentro da opção `Modo legado` na barra lateral. Ele mantém o fluxo anterior com CSV agregado, CSV detalhado, cálculos, auditoria de indicadores, editor de ícones/cores e templates institucionais.

## Demonstração

No modo padrão, use `Carregar matriz institucional vazia` para testar uma imagem-base pronta e depois carregue ou crie campos.

No modo legado, use o botão `Carregar exemplo de demonstração` para ver um exemplo fictício já configurado. A interface exibirá um aviso de modo de demonstração. Esse aviso é apenas da interface e não aparece em exportações feitas com CSVs próprios.

Os arquivos demonstrativos ficam em `examples/`.

## CSV agregado e CSV detalhado

CSV agregado: cada linha já representa um indicador. Exemplo:

```csv
Indicador;Valor
Laboratórios ativos;14
Projetos apoiados;87
Bolsas concedidas;1.240
```

Quando esse formato é detectado com segurança, a ferramenta oferece criar automaticamente um card por linha. A primeira coluna vira rótulo e a segunda vira valor direto.

CSV detalhado: cada linha representa uma ocorrência ou registro. Exemplo:

```csv
unidade;projeto;municipio;ano;valor;perfil
Norte;Alfa;Salvador;2026;10;ativo
Sul;Beta;Ilhéus;2026;20;ativo
```

Nesse caso, crie os indicadores manualmente e escolha operações como soma, contagem, contagem distinta, média, percentual, valor direto ou último valor.

## Geração automática offline

Depois de carregar um CSV, a ferramenta oferece dois caminhos:

- `Gerar infográfico automaticamente`
- `Configurar manualmente`

A geração automática não usa LLMs, OpenAI API, internet ou serviços externos. Ela roda inteiramente local, usando:

- regras em YAML;
- normalização de acentos, pontuação e espaços;
- heurísticas simples de singular/plural;
- dicionário de abreviações;
- sinônimos e termos negativos;
- classificação de colunas;
- correspondência aproximada por biblioteca padrão do Python;
- pontuação de confiança;
- validações para evitar operações inseguras.

O modo manual permanece disponível antes e depois da geração automática.

## Motor de regras

As regras institucionais ficam em:

```text
config/semantic_rules.yaml
```

As regras aprendidas pelo uso ficam em:

```text
config/custom_semantic_rules.yaml
```

Cada regra pode definir termos, sinônimos, termos negativos, categoria, seção, ícone, cor, prioridade, confiança mínima, rótulo preferencial e operações compatíveis.

Regras personalizadas têm prioridade sobre regras padrão. O arquivo institucional não é alterado silenciosamente.

## Confiança e revisão

Antes de aplicar qualquer sugestão, a ferramenta mostra `Revisar configuração automática`.

Para cada indicador, a revisão exibe:

- rótulo;
- valor ou cálculo;
- coluna de origem;
- operação;
- filtro;
- seção;
- ícone;
- cor;
- ordem;
- confiança;
- motivo da escolha.

Níveis de confiança:

- `85–100`: alta;
- `60–84`: média;
- abaixo de `60`: baixa, não aplicada automaticamente.

Na revisão, você pode escolher:

- `Aceitar tudo`;
- `Aceitar somente alta confiança`;
- `Editar configuração`;
- `Cancelar`;
- `Gerar novamente`.

Depois de aceitar, todos os editores manuais continuam disponíveis.

## Selecionar design

Depois de configurar ou gerar os indicadores, a interface mostra a seção `Selecionar design`.

Neste momento existe somente um design público:

- `institucional_claro_v1`;
- nome: `Institucional claro`;
- versão: `1.0`;
- capacidade: até 9 indicadores por página;
- composição: 4 indicadores principais, 2 indicadores intermediários e 3 indicadores complementares.

A miniatura exibida na galeria usa a referência visual polida e aparece identificada na interface como `Referência visual — dados fictícios`. Essa imagem serve apenas para escolha visual do design. Ela não é usada como fundo de exportação.

A escolha do design é salva no YAML:

```yaml
template:
  id: institucional_claro_v1
  version: "1.0"
```

Se o design selecionado não puder ser carregado, a ferramenta mostra um aviso e usa o renderer de compatibilidade.

## Matriz, referência e thumbnail

O template institucional claro usa três tipos de imagem:

- matriz de produção: fundo limpo usado na exportação;
- referência visual: imagem preenchida com dados fictícios, usada para comparação e extração de ícones;
- thumbnail: miniatura da referência, usada somente na galeria de designs.

O renderer de produção nunca usa a referência preenchida como fundo. Os valores, rótulos, títulos, seções, fonte e chamada final vêm do CSV, da configuração YAML ou dos campos preenchidos pelo usuário.

Na versão atual do template institucional claro, a logomarca do Observatório não é desenhada no topo. O cabeçalho textual institucional ocupa essa função para manter o layout limpo e próximo da matriz aprovada.

Os arquivos ficam em:

```text
assets/templates/institucional_claro_v1/base_9_indicadores.png
assets/templates/institucional_claro_v1/thumbnail.png
assets/references/institucional_claro_v1_referencia.png
assets/icons/institucional_claro_v1/
```

## CSV agregado no modo automático

Quando cada linha já representa um indicador e seu valor pronto, a ferramenta:

- cria um card por linha;
- usa `valor direto`;
- preserva o valor textual exatamente como veio do CSV;
- não inventa unidade;
- sugere seção, ícone, cor e ordem pelas regras semânticas;
- usa azul institucional como fallback.

## CSV detalhado no modo automático

Quando cada linha representa um registro, a ferramenta classifica colunas como identificador, categoria, número, percentual, booleano, data, texto livre, possível informação pessoal, localização ou instituição.

Operações só são sugeridas quando há segurança suficiente. A ferramenta evita:

- somar códigos, matrículas, anos e identificadores;
- expor nomes ou dados pessoais como texto público;
- transformar texto livre em indicador automático;
- usar soma apenas porque uma coluna parece numérica.

## Aprendizado por regras

Depois de corrigir manualmente seção, ícone, cor ou rótulo de um indicador, use:

```text
Salvar esta correção como regra
```

A correção será salva em `config/custom_semantic_rules.yaml` com:

- termo detectado;
- seção escolhida;
- ícone escolhido;
- cor;
- rótulo público;
- operação.

Na barra lateral, a área `Regras personalizadas` permite visualizar, editar, salvar e exportar o YAML de regras personalizadas.

## Criar indicadores

Depois de carregar um CSV:

1. Confira colunas, tipos inferidos, ausências e prévia.
2. Escolha começar vazio, carregar YAML compatível ou criar cards de CSV agregado.
3. Use `Adicionar indicador` para criar um card.
4. Edite rótulo, seção, coluna, operação, filtros, prefixo, sufixo, casas decimais, ícone e cor.
5. Use os controles de duplicar, excluir e reordenar.
6. Configure a ordem das seções e se o título da seção deve aparecer.

A prévia só é gerada quando existe pelo menos um indicador válido.

## YAML

O YAML salva textos institucionais, indicadores, operações, filtros, seções, ordenação, cores, ícones, exportação e assinatura das colunas do CSV.

Ao carregar um YAML incompatível com o CSV atual, a interface informa quais colunas estão ausentes e não aplica o mapeamento em silêncio.

## Exportação

Os arquivos gerados ficam em `output/` com nomes derivados do CSV e da data, por exemplo:

- `infografico_planilha_final_2026-08-25.png`
- `infografico_planilha_final_2026-08-25.pdf`
- `auditoria_planilha_final_2026-08-25.csv`

Se houver indicadores demais para uma página, a ferramenta oferece geração em múltiplas páginas.

O template `institucional_claro_v1` gera páginas com até 9 indicadores. Ao ultrapassar esse limite, a exportação cria páginas adicionais e repete cabeçalho, rodapé, seções e auditoria de forma consistente.

O nome do arquivo CSV não é usado automaticamente como fonte pública. No infográfico, a linha `Fonte` usa somente o campo institucional preenchido pelo usuário. Se esse campo estiver vazio, a linha é omitida e a interface avisa antes da exportação; o nome do CSV permanece registrado apenas na auditoria.

## Auditoria

A auditoria registra, para cada indicador:

- coluna utilizada;
- filtro aplicado;
- operação realizada;
- valor bruto;
- valor exibido;
- período informado;
- fonte.

Use esse arquivo para conferir que cada número veio do CSV ou de uma operação configurada.

Quando uma configuração automática é aceita, a exportação também pode gerar uma auditoria de inferência com regra utilizada, confiança, justificativa, configuração original e se a decisão veio do modo automático.

A auditoria principal também registra o template, a versão do template, a página, a seção, o slot, o ícone usado e se houve fallback visual.

O arquivo CSV carregado é registrado na coluna `arquivo CSV`, separada da fonte institucional exibida no infográfico.

## Acervo versionado

A tela inicial agora possui abas para uso recorrente:

- `Infográficos`: lista projetos salvos no acervo, mostra revisão, campos e atualizações disponíveis.
- `Dados`: cadastra conjuntos de dados e publica novas versões de CSV.
- `Imagens-base`: cadastra PNG/JPG e separa base limpa de produção de referência preenchida.
- `Catálogo`: mantém definições reutilizáveis de indicadores, sem valores embutidos.
- `Backup`: gera um ZIP local com metadados e arquivos do acervo.

O acervo local fica em `storage/acervo/` e é ignorado pelo Git. Ele serve para desenvolvimento e uso local. Para produção online recorrente, configure um backend persistente como Supabase usando `docs/producao_acervo.md` e a migração em `supabase/migrations/`.

## Atualização por versão de CSV

O fluxo recomendado é cadastrar o conjunto uma vez e publicar novas versões no mesmo cadastro. Quando uma versão válida nova é ativada, os infográficos vinculados aparecem como pendentes de atualização.

Ao atualizar, a ferramenta:

- resolve a versão ativa do conjunto;
- recalcula campos e séries de gráficos;
- preserva posição, tamanho, fonte, cor, textos manuais e imagem-base;
- registra a nova revisão do infográfico;
- bloqueia a atualização se houver duplicata, campo ausente, valor incompatível ou vínculo ambíguo.

O layout não é reconstruído do zero. A atualização muda os dados, não o desenho.

## Gráficos no canvas

O modo imagem-base agora aceita gráficos como elementos editáveis. É possível inserir:

- barras horizontais;
- colunas verticais.

O gráfico entra na mesma tabela de campos, pode ser arrastado para a arte, movido, redimensionado, removido e exportado no PNG/PDF final. A escala é compartilhada dentro da série; cada barra não é desenhada como se fosse 100%.

Os gráficos podem usar uma lista de indicadores do catálogo ou uma série sintética/dimensional preparada no CSV. Para produção, declare as dimensões e evite transformar ausências em zero.

## Formato longo recomendado

Para novos CSVs recorrentes, use:

```csv
indicador_id,periodo,recorte_id,valor
pesquisadores_ativos,2021-2026,bahia_total,1234
grupos_pesquisa,2021-2026,bahia_total,87
```

CSVs agregados e detalhados antigos continuam funcionando. Quando o CSV não tiver `indicador_id`, a ferramenta pode sugerir vínculos por rótulo/alias, mas ambiguidades precisam de revisão humana.

## Supabase

A estrutura remota usa PostgreSQL para metadados e Supabase Storage para CSVs e imagens-base. O projeto não inclui credenciais reais.

Quando `archive.provider = "supabase"` estiver configurado nos secrets, a tela inicial passa a usar o acervo compartilhado. No modelo simples recomendado, a equipe entra com uma senha da própria ferramenta no Streamlit; ninguém precisa abrir o painel do Supabase nem ter conta individual no Supabase para publicar CSV, imagem-base ou nova versão de dados.

Arquivos relevantes:

- `supabase/migrations/202609020001_acervo_infograficos.sql`
- `.streamlit/secrets.toml.example`
- `docs/producao_acervo.md`
- `docs/referencias_visuais.md`

Fluxo para a equipe:

1. Abrir o link do Streamlit.
2. Digitar a senha da equipe.
3. Na aba `Dados`, cadastrar ou publicar nova versão de CSV.
4. Na aba `Imagens-base`, cadastrar a arte limpa.
5. Na aba `Infográficos`, abrir, atualizar ou gerar as peças.
6. No editor, salvar no acervo para que outra pessoa autorizada consiga reabrir depois.

Na aba `Imagens-base`, é possível enviar uma ou várias imagens de uma vez.

- `Base limpa de produção`: arte sem números, textos variáveis ou barras já preenchidas. É a imagem usada de verdade para gerar o infográfico.
- `Referência preenchida`: arte exemplo com números e textos já desenhados. Serve como guia visual ou miniatura, mas não deve ser usada como fundo final de produção.

## Ícones do template

O design institucional claro possui nove ícones extraídos da referência visual:

- pesquisadores;
- grupos de pesquisa;
- pós-graduação;
- instituições;
- produção científica;
- municípios;
- doutorado;
- bolsa de produtividade;
- produção técnica.

Esses ícones são selecionados semanticamente por rótulo ou pelo ícone escolhido no editor de aparência. Quando não houver correspondência, a ferramenta usa a biblioteca atual de ícones e marca o caso como `Ícone de fallback — revisão recomendada` na auditoria.

## Como criar um novo template

Para adicionar um segundo design no futuro:

1. Crie uma pasta em `src/templates/novo_template/`.
2. Implemente um `get_template(metadata, manifest)` no `__init__.py`.
3. Crie o renderer próprio do design.
4. Defina layout, posições, tipografia, capacidade e validações em arquivos do próprio template.
5. Adicione um manifesto em `config/templates/novo_template.yaml`.
6. Adicione thumbnail e assets em `assets/templates/novo_template/`.
7. Adicione referências em `assets/references/`, quando necessário.
8. Adicione ícones específicos em `assets/icons/novo_template/`, se existirem.
9. Escreva testes de descoberta, manifesto, renderização, paginação e auditoria.
10. Execute a suíte completa de testes.

O `app.py` consulta o registro de templates. Portanto, um novo design não deve exigir grandes blocos `if/elif` no aplicativo.

## Testes

Execute:

```powershell
.\.venv\Scripts\python -m pytest
```

Os testes cobrem CSVs agregados e detalhados, codificações, formatação brasileira, operações estatísticas, YAML, layout, exportação, regras semânticas, confiança, classificação de colunas, regras personalizadas e ausência de conteúdo fictício fora das áreas permitidas.

Também há testes para descoberta de templates, manifesto, thumbnail, persistência do template no YAML, uso da matriz limpa, proibição de usar a referência como fundo, extração de ícones, paginação e auditoria com template/página/slot.

A camada de produção acrescenta testes de catálogo, versionamento de conjuntos, idempotência, bloqueio de duplicatas, preservação de layout na atualização v1/v2 e renderização de gráficos no canvas.
