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
