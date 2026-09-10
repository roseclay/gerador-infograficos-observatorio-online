# Operacao local e continuidade

## Principio

O aplicativo e local e orientado a arquivos. Um infografico e identificado por um JSON em `workspace/infograficos/`, acompanhado pela imagem-base e pelo CSV vinculados. Nao existe sincronizacao automatica entre computadores.

## Compartilhar um trabalho

Use o comando de baixar o projeto em ZIP como backup ou transferencia manual. Para recupera-lo em outra instalacao, extraia o conteudo dentro da pasta `workspace/`, preservando a estrutura `infograficos/`, `imagens/` e `dados/`, e reinicie a aplicacao. Ainda nao existe importacao do ZIP pela interface. Outra opcao e transferir a pasta `workspace/` inteira por um canal institucional.

Salvar um JSON nao publica nem sincroniza o trabalho. O modelo foi escolhido para uma equipe pequena trabalhar offline em uma pasta controlada. Para acesso simultaneo por computadores diferentes, a pasta precisa estar em um servidor com volume persistente ou ser transferida de forma manual; a especificacao atual proibe usar banco remoto como fonte de verdade.

## Backup

Inclua no backup:

- `workspace/infograficos/`;
- `workspace/imagens/`;
- `workspace/dados/`;
- `workspace/exportacoes/`, quando os arquivos finais precisarem ser preservados.

O codigo-fonte pode ser recuperado pelo Git, mas `workspace/` e intencionalmente ignorado e precisa de backup separado.

## Hospedagem com disco efemero

Algumas plataformas gratuitas recriam o sistema de arquivos ao suspender ou atualizar o aplicativo. Nesses ambientes, trabalhos salvos podem desaparecer. O aplicativo mostra um aviso quando detecta esse contexto. Antes de fechar a sessao, baixe o ZIP do projeto.

Para uso continuo por uma equipe, execute o aplicativo em um computador ou servidor com volume persistente e defina `INFOGRAPHICS_WORKSPACE` para esse volume.

```powershell
$env:INFOGRAPHICS_WORKSPACE = "D:\Dados\GeradorInfograficos"
streamlit run app.py
```

## Atualizacao dos dados

1. Abra o trabalho.
2. Escolha **Atualizar dados**.
3. Selecione o CSV novo.
4. Confira valores alterados, ausentes e incompatibilidades.
5. Confirme a atualizacao.
6. Resolva campos pendentes antes de exportar.

Valores ausentes nunca sao convertidos em zero. O valor anterior e preservado para comparacao, mas a exportacao permanece bloqueada.

## Integridade

- caminhos gravados no JSON sao relativos ao workspace;
- caminhos que tentam sair do workspace sao rejeitados;
- o salvamento usa arquivo temporario e substituicao atomica;
- IDs de campo permanecem estaveis entre salvamentos;
- checksums registram a imagem-base e o CSV;
- timestamps registram criacao, atualizacao e versao do esquema;
- um JSON invalido e isolado na tela inicial sem impedir a abertura dos demais.
