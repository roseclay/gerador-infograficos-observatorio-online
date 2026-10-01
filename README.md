# Estudio de Infograficos do Observatorio

Ferramenta local para montar infograficos sobre uma imagem-base, ligar textos e graficos a dados de CSV e exportar o resultado em PNG ou PDF. O editor foi pensado para equipes que precisam atualizar numeros sem reconstruir a arte.

## O que a ferramenta faz

- usa uma imagem-base PNG ou JPG como fundo real do infografico;
- importa campos de um CSV para uma mesa lateral;
- permite arrastar os campos para o canvas;
- move elementos com o mouse ou com as setas do teclado;
- redimensiona textos diretamente no canvas;
- cria graficos de barras horizontais e colunas verticais;
- preserva posicoes, estilos, vinculos e textos manuais durante atualizacoes;
- mostra uma conferencia das mudancas antes de trocar os dados;
- bloqueia a exportacao quando um campo vinculado deixou de existir;
- salva cada infografico em um JSON local autocontido por referencias de arquivo;
- reabre trabalhos salvos e gera PNG e PDF com o mesmo renderer da previa;
- empacota cada projeto em ZIP para backup ou transferencia manual.

Nao ha banco remoto, autenticacao, sincronizacao nem dependencia de servicos externos. Os arquivos de demonstracao em `examples/` nao representam dados institucionais reais.

## Instalacao

No Windows, execute `instalar.bat`. Para instalar manualmente:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Como iniciar

Execute `iniciar.bat` ou:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Abra o endereco informado pelo Streamlit, normalmente `http://localhost:8501`.

## Rodar com Docker

Para servidores do Observatorio ou maquinas que ja tenham Docker instalado:

```bash
docker build -t gerador-infograficos-observatorio .
docker run --rm -p 8501:8501 \
  -v "$(pwd)/workspace:/app/workspace" \
  -v "$(pwd)/output:/app/output" \
  gerador-infograficos-observatorio
```

Com Docker Compose:

```bash
docker compose up --build -d
```

Depois acesse `http://localhost:8501`. Em um servidor publico, a equipe de infraestrutura pode apontar um proxy ou subcaminho institucional para a porta `8501`.

## Fluxo recomendado

1. Na tela inicial, clique em **Novo**.
2. Informe um nome para o trabalho.
3. Carregue a imagem-base.
4. Carregue o CSV de campos.
5. Use **Filtrar campos** somente quando precisar reduzir a lista por nome ou categoria.
6. Arraste cada campo da tabela para o canvas.
7. Ajuste posicao, tamanho, fonte, cor e alinhamento.
8. Adicione graficos quando o CSV contiver categorias e valores numericos.
9. Clique em **Salvar**.
10. Use **Exportar** para gerar PNG ou PDF.

O campo **Fonte dos dados** registra a origem institucional no JSON e na auditoria dos campos. No modo imagem-base, ele nao escreve automaticamente sobre a arte: o rodape visual deve fazer parte da imagem-base. O nome do CSV fica apenas nos metadados internos.

## Atualizar os dados

Abra um infografico e clique em **Atualizar dados**. Selecione o novo CSV e confira a previa:

- valores alterados aparecem antes da confirmacao;
- campos ausentes mantem o valor anterior e ficam marcados como pendentes;
- textos manuais, imagem-base, coordenadas, tamanhos e estilos nao mudam;
- graficos vinculados sao recalculados com a mesma escala e configuracao;
- a exportacao fica bloqueada enquanto houver vinculos pendentes.

Uma atualizacao so e aplicada depois da confirmacao explicita.

## Graficos

O editor oferece barras horizontais e colunas verticais. Ambos partem de zero, respeitam a escala real dos valores e guardam no JSON as colunas de categoria e valor, o tipo, as cores, a posicao e o tamanho. Rotulos longos sao ajustados para evitar cortes.

## Arquivos locais

```text
workspace/
  infograficos/
    <id>.json
  imagens/
    infograficos/
      <id>/
        base.png
  dados/
    <id>.csv
    catalogo.json
  exportacoes/
```

Cada JSON usa IDs estaveis e caminhos relativos. Imagens e CSVs nao sao gravados em base64. A gravacao e atomica para evitar arquivos parcialmente escritos.

O diretorio `workspace/` e ignorado pelo Git. Preserve-o em backup. Em hospedagens que apagam o disco ao reiniciar, baixe o ZIP do projeto antes de encerrar a sessao.

### O que "salvar em JSON" significa

O JSON substitui o banco de dados para uma operacao editorial pequena e local. Ele descreve um unico infografico; a imagem-base e o CSV ficam em arquivos separados, referenciados por caminhos relativos. A tela inicial descobre esses JSONs e monta a lista de trabalhos.

Isso nao e sincronizacao em nuvem. Em computadores diferentes, os projetos so ficam iguais quando a pasta `workspace/` ou o pacote ZIP e transferido por um canal institucional. No Streamlit Community Cloud, cada sessao usa uma area temporaria separada, para que os trabalhos de visitantes diferentes nao se misturem. Arquivos criados durante o uso podem desaparecer depois de suspensao, reinicio, encerramento da sessao ou nova publicacao; por isso, baixe o pacote ZIP antes de sair.

## Testes

```powershell
python -m pytest -q
```

Os testes cobrem persistencia, validacao de caminhos, atualizacao de dados, preservacao de layout, graficos, exportacao e interface principal.

Detalhes operacionais: [docs/producao_local.md](docs/producao_local.md).
