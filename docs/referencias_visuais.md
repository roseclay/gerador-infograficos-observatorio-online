# Referências visuais info01 a info05

As imagens `info01.png` a `info05.png` são referências preenchidas. Elas não são bases limpas, não devem ser usadas como fundo de produção e não carregam valores oficiais para o sistema.

## Perfil 01: A ciência baiana em números

Elementos variáveis esperados:

- pesquisadores ativos;
- grupos de pesquisa;
- programas de pós-graduação;
- instituições de ensino e pesquisa;
- produção científica total;
- percentual com doutorado;
- bolsistas de produtividade;
- produção técnica total;
- fonte, período e data de atualização.

Para transformar em base limpa, remova valores, percentuais, rótulos variáveis e qualquer geometria que codifique dados.

## Perfil 02: Quanto a Bahia produz

Elementos variáveis esperados:

- produção científica total;
- gráfico horizontal de artigos, trabalhos em eventos, capítulos de livro, livros e textos em revista;
- produção técnica total;
- relatórios técnicos;
- programas de computador;
- depósitos de patentes;
- registros de marcas;
- fonte, período e data de atualização.

As barras azuis e seus comprimentos precisam sair da base limpa, porque serão gerados pelo renderer.

## Perfil 03: Ciência que vira tecnologia

Elementos variáveis esperados:

- produção técnica total;
- relatórios técnicos;
- programas de computador;
- depósitos de patentes;
- registros de marcas;
- textos institucionais editáveis;
- fonte, período e data de atualização.

Quadros, divisórias neutras e decoração podem permanecer se não codificarem valores.

## Perfil 04: Excelência reconhecida

Elementos variáveis esperados:

- total de pesquisadores com bolsa de produtividade;
- bolsistas PQ;
- bolsistas DT;
- texto de explicação institucional, se a equipe decidir que será editável;
- fonte, período e data de atualização.

PQ e DT devem permanecer separados. O total não deve ser calculado como soma automática sem regra explícita de deduplicação.

## Perfil 05: Quem faz ciência aqui

Elementos variáveis esperados:

- pesquisadores ativos;
- percentual com doutorado;
- gráfico horizontal de doutorado, mestrado e especialização;
- fonte, período e data de atualização.

Formação acadêmica exige definição do universo: maior titulação por pessoa, pessoas com determinado título ou títulos registrados.

## Checklist para bases limpas

- Remover números, percentuais, datas e períodos variáveis.
- Remover rótulos que possam mudar por CSV ou catálogo.
- Remover barras, colunas, eixos e qualquer forma cujo tamanho represente valor.
- Preservar apenas fundo, identidade visual, molduras neutras, mapa e ornamentos que não representem dados.
- Cadastrar referência preenchida como `referência`, nunca como `base limpa de produção`.
