# Gerador de infográficos institucionais

Ferramenta local para produzir infográficos institucionais a partir de uma imagem-base ou, no modo avançado, a partir de indicadores configurados em CSV. O fluxo padrão é simples: a pessoa carrega uma arte pronta, posiciona campos de texto sobre ela e exporta a imagem final em PNG/PDF.

O design segue a identidade visual aprovada pela SECTI, mas números, textos, seções e indicadores são definidos exclusivamente pelo CSV e pelas configurações do usuário.

## Conceito do projeto

- O modo padrão usa a imagem enviada como base real da exportação.
- No modo avançado de templates, imagens de referência continuam sendo apenas referência visual.
- O CSV de demonstração contém dados fictícios e serve somente para testar a ferramenta.
- A aplicação inicia vazia e não carrega automaticamente exemplos.
- A geração é determinística: a mesma imagem-base, o mesmo CSV/YAML e as mesmas coordenadas produzem o mesmo resultado.
- O modo padrão com imagem-base, campos arrastáveis e prévias por campo é a versão estável elegível para produção.

## Funcionalidades

- Carregamento de imagem-base em PNG ou JPG.
- Drag-and-drop de campos do CSV para o editor visual.
- Movimento dos campos com mouse ou setas do teclado.
- Redimensionamento da área de texto com o mouse.
- Remoção de textos posicionados no editor.
- Exportação em PNG e PDF.
- Salvamento de configurações em YAML.
- Leitura de CSV agregado ou detalhado no modo avançado.
- Geração automática local baseada em regras.
- Configuração manual de indicadores, seções, ícones e cores.
- Auditoria da origem e do cálculo de cada valor.

## Requisitos

- Windows;
- Python 3.10 ou superior;
- PowerShell ou Prompt de Comando.

Entre na pasta do projeto antes de executar comandos:

```powershell
cd gerador-infograficos-observatorio
```

## Instalação

Clique duas vezes em:

```text
instalar.bat
```

Ou execute:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Inicialização

Clique duas vezes em:

```text
iniciar.bat
```

Ou execute:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

A ferramenta abrirá normalmente em:

```text
http://localhost:8501
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

## Modo avançado: indicadores por CSV

Use o seletor `Modo de criação` na barra lateral para acessar `Indicadores por CSV (avançado)`. Esse modo mantém o fluxo anterior com CSV agregado, CSV detalhado, cálculos, auditoria de indicadores, editor de ícones/cores e templates institucionais.

## Demonstração

No modo padrão, use `Carregar matriz institucional vazia` para testar uma imagem-base pronta e depois carregue ou crie campos.

No modo avançado, use o botão `Carregar exemplo de demonstração` para conhecer o funcionamento da aplicação usando dados fictícios armazenados em:

```text
examples/
```

Esses arquivos servem apenas para demonstração e não devem ser tratados como dados reais.

## Formatos de CSV

### CSV agregado

Cada linha contém um indicador já calculado:

```csv
Indicador;Valor
Laboratórios ativos;14
Projetos apoiados;87
Bolsas concedidas;1.240
```

Nesse formato, a ferramenta pode criar automaticamente um card por linha, usando a primeira coluna como rótulo, a segunda como valor e a operação `valor direto`.

### CSV detalhado

Cada linha representa um registro individual:

```csv
unidade;projeto;municipio;ano;valor;perfil
Norte;Alfa;Salvador;2026;10;ativo
Sul;Beta;Ilhéus;2026;20;ativo
```

Os indicadores podem utilizar:

- soma;
- contagem;
- contagem distinta;
- média;
- percentual;
- valor direto;
- último valor.

## Geração automática offline

Após carregar um CSV, escolha entre:

- **Gerar infográfico automaticamente**;
- **Configurar manualmente**.

A geração automática funciona localmente e não utiliza LLM, API externa, OpenAI ou internet. O motor utiliza regras YAML, sinônimos, normalização de texto, classificação de colunas, pontuação de confiança e proteções contra cálculos inadequados.

Antes de aplicar uma configuração automática, a ferramenta apresenta:

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
- justificativa da sugestão.

Níveis de confiança:

- `85-100`: alta;
- `60-84`: média;
- abaixo de `60`: baixa.

É possível aceitar tudo, aceitar somente sugestões de alta confiança, editar, cancelar ou gerar novamente. Depois de aceitar, todos os editores manuais continuam disponíveis.

## Regras semânticas

Regras padrão:

```text
config/semantic_rules.yaml
```

Regras criadas durante o uso:

```text
config/custom_semantic_rules.yaml
```

As regras podem definir termos, sinônimos, rótulo público, seção, ícone, cor, operação, prioridade e confiança mínima. Regras personalizadas têm prioridade sobre as regras padrão.

Depois de corrigir manualmente seção, ícone, cor ou rótulo de um indicador, use `Salvar esta correção como regra` para reaproveitar a decisão em novos CSVs.

## Selecionar design

Depois de configurar ou gerar os indicadores, a interface mostra a seção `Selecionar design`.

Neste momento existe somente um design público:

- `institucional_claro_v1`;
- nome: `Institucional claro`;
- versão: `1.0`;
- capacidade: até 9 indicadores por página;
- composição: 4 indicadores principais, 2 indicadores intermediários e 3 indicadores complementares.

A miniatura exibida na galeria usa a referência visual polida e aparece identificada na interface como `Referência visual - dados fictícios`. Essa imagem serve apenas para escolha visual do design. Ela não é usada como fundo de exportação.

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

## Fluxo recomendado no modo avançado

1. Carregue o CSV.
2. Confira separador, codificação e cabeçalho.
3. Escolha a geração automática ou a configuração manual.
4. Revise as sugestões e os cálculos.
5. Ajuste rótulos, seções, ícones e cores.
6. Preencha cabeçalho, título, subtítulo, período, fonte, data, chamada final e endereço eletrônico.
7. Confira a prévia.
8. Salve a configuração, se desejar reutilizá-la.
9. Exporte o infográfico e a auditoria.

## Exportação

Os arquivos são gerados em:

```text
output/
```

Exemplos:

```text
infografico_planilha_final_2026-08-25.png
infografico_planilha_final_2026-08-25.pdf
auditoria_planilha_final_2026-08-25.csv
```

Quando necessário, o conteúdo pode ser distribuído em múltiplas páginas.

O template `institucional_claro_v1` gera páginas com até 9 indicadores. Ao ultrapassar esse limite, a exportação cria páginas adicionais e repete cabeçalho, rodapé, seções e auditoria de forma consistente.

O nome do arquivo CSV não é usado automaticamente como fonte pública. No infográfico, a linha `Fonte` usa somente o campo institucional preenchido pelo usuário. Se esse campo estiver vazio, a linha é omitida e a interface avisa antes da exportação; o nome do CSV permanece registrado apenas na auditoria.

## Auditoria

A auditoria pode registrar:

- indicador;
- coluna utilizada;
- filtro aplicado;
- operação;
- valor bruto;
- valor exibido;
- período;
- fonte;
- decisões da geração automática;
- template;
- versão do template;
- página;
- seção;
- slot;
- ícone usado;
- fallback visual, quando houver.

Use-a para confirmar que cada número veio do CSV ou de uma operação explicitamente configurada.

O arquivo CSV carregado é registrado na coluna `arquivo CSV`, separada da fonte institucional exibida no infográfico.

## Integridade dos dados

A ferramenta não deve:

- inventar valores ausentes;
- preencher cards com números ilustrativos;
- produzir conclusões sem sustentação;
- expor nomes ou dados pessoais;
- somar códigos, matrículas, anos ou identificadores;
- criar rankings institucionais sem configuração explícita.

A referência visual orienta somente o design e nunca é utilizada como fonte de dados.

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

Esses ícones são selecionados semanticamente por rótulo ou pelo ícone escolhido no editor de aparência. Quando não houver correspondência, a ferramenta usa a biblioteca atual de ícones e marca o caso como `Ícone de fallback - revisão recomendada` na auditoria.

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

Os testes cobrem CSVs agregados e detalhados, codificações, formatação brasileira, operações estatísticas, YAML, layout, exportação, regras semânticas, confiança, classificação de colunas, regras personalizadas, ausência de conteúdo fictício fora das áreas permitidas, descoberta de templates, manifesto, thumbnail, persistência do template no YAML, uso da matriz limpa, proibição de usar a referência como fundo, extração de ícones, paginação e auditoria com template/página/slot.

## Estrutura do projeto

```text
app.py             Interface Streamlit
src/               Código da aplicação
config/            Regras e configurações
assets/            Logos e recursos visuais
examples/          Dados fictícios de demonstração
tests/             Testes automatizados
output/            Arquivos gerados localmente
requirements.txt   Dependências Python
instalar.bat       Instalação no Windows
iniciar.bat        Inicialização da ferramenta
```

## Responsabilidade de publicação

Antes de publicar qualquer infográfico, revise o CSV, os filtros, os cálculos, os textos institucionais, a fonte e a auditoria. A ferramenta auxilia a produção visual, mas a responsabilidade final pelos dados publicados permanece com a equipe responsável.
