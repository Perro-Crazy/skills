# Parâmetro `Modifier`

## Antes

```kotlin
@Composable
fun StatusBadge(mod: Modifier, label: String) {
    Row(modifier = mod) {
        Icon(Icons.Default.Check, contentDescription = null, modifier = mod)
        Text(label, modifier = mod)
    }
}
```

Problemas: `mod` (1) não é chamado `modifier`, (2) não tem default, e (3) a mesma
instância é passada para três emissores diferentes (`Row`, `Icon`, `Text`) — qualquer
`padding`/`clickable` que o chamador aplique se repete nos três, em vez de afetar só o
container raiz.

## Depois

```kotlin
@Composable
fun StatusBadge(label: String, modifier: Modifier = Modifier) {
    Row(modifier = modifier) {
        Icon(Icons.Default.Check, contentDescription = null)
        Text(label)
    }
}
```

## Por quê

Só o elemento raiz (`Row`) precisa do `Modifier` recebido de fora — os filhos internos
(`Icon`, `Text`) não devem herdar automaticamente os ajustes que o chamador pediu para
o componente como um todo (ex.: `StatusBadge(modifier = Modifier.padding(8.dp))` deveria
adicionar padding ao redor do badge inteiro, não a cada ícone/texto individualmente).
Renomear para `modifier` e adicionar o default `= Modifier` também torna o componente
utilizável sem precisar passar nada explicitamente no caso comum.

---

## Bônus: múltiplos parâmetros `Modifier`

```kotlin
// Antes
@Composable
fun IconLabel(
    icon: Painter,
    label: String,
    iconModifier: Modifier = Modifier,
    labelModifier: Modifier = Modifier,
) {
    Row {
        Icon(icon, contentDescription = null, modifier = iconModifier)
        Text(label, modifier = labelModifier)
    }
}

// Depois
@Composable
fun IconLabel(icon: Painter, label: String, modifier: Modifier = Modifier) {
    Row(modifier = modifier) {
        Icon(icon, contentDescription = null)
        Text(label)
    }
}
```

Dois parâmetros `Modifier` na assinatura pública força quem chama a decidir como
combiná-los — e na prática, a maioria das customizações que alguém precisa fazer é no
container como um todo, não em `Icon`/`Text` individualmente. Um único `modifier`
aplicado no `Row` cobre o caso comum; se um dia for genuinamente necessário customizar
o ícone separadamente, isso pode virar uma sobrecarga específica, não o padrão default.

---

## Bônus: ordem de encadeamento do `modifier` recebido

```kotlin
// Antes — modifier do chamador aplicado por último (precedência invertida)
@Composable
fun Highlighted(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(modifier = Modifier.background(Color.Yellow).padding(4.dp).then(modifier)) {
        content()
    }
}

// Depois
@Composable
fun Highlighted(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(modifier = modifier.background(Color.Yellow).padding(4.dp)) {
        content()
    }
}
```

Com `.then(modifier)` no final, um `Highlighted(modifier = Modifier.size(100.dp))`
teria seu `size` aplicado *depois* do `background`/`padding` internos — o que em
alguns casos até funciona por acaso, mas inverte a expectativa de que o `modifier` do
chamador é o ponto de partida da cadeia, com prioridade sobre os ajustes internos do
componente.
