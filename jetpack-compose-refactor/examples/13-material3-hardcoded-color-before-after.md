# Theming do Material 3: cor e tipografia fixas vs. `MaterialTheme`

## Cor construída inline

```kotlin
// Antes — cor fixa não reage a dark theme nem a dynamic color
@Composable
fun PriceTag(price: String, modifier: Modifier = Modifier) {
    Text(
        text = price,
        color = Color(0xFF6650A4),
        modifier = modifier,
    )
}

// Depois — token do tema
@Composable
fun PriceTag(price: String, modifier: Modifier = Modifier) {
    Text(
        text = price,
        color = MaterialTheme.colorScheme.primary,
        modifier = modifier,
    )
}
```

## Constante de cor nomeada

```kotlin
// Antes
@Composable
fun ErrorBanner(message: String) {
    Surface(color = Color.Red) {
        Text(message, color = Color.White)
    }
}

// Depois
@Composable
fun ErrorBanner(message: String) {
    Surface(color = MaterialTheme.colorScheme.errorContainer) {
        Text(message, color = MaterialTheme.colorScheme.onErrorContainer)
    }
}
```

## Exceção: o próprio composable de tema

O composable que **define** o `ColorScheme` do app é o lugar certo para os literais —
o scanner reconhece esse padrão (nome terminando em `Theme`, ou corpo chamando
`lightColorScheme`/`darkColorScheme`/`dynamicLightColorScheme`/`dynamicDarkColorScheme`)
e não reporta finding aqui:

```kotlin
private val Purple40 = Color(0xFF6650A4)
private val PurpleGrey40 = Color(0xFF625b71)

@Composable
fun AppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) {
        darkColorScheme(primary = Purple40.copy(alpha = 0.8f))
    } else {
        lightColorScheme(primary = Purple40, secondary = PurpleGrey40)
    }
    MaterialTheme(colorScheme = colorScheme, content = content)
}
```

## Exceção: `Color.Transparent`/`Color.Unspecified`

```kotlin
// Não dispara finding — sem equivalente em colorScheme, uso legítimo
Brush.verticalGradient(listOf(MaterialTheme.colorScheme.surface, Color.Transparent))
```

## Tipografia inline

```kotlin
// Antes — reinventa a escala tipográfica caso a caso
@Composable
fun SectionTitle(text: String) {
    Text(text = text, fontSize = 22.sp, fontFamily = FontFamily.Serif)
}

// Depois — usa a escala do tema
@Composable
fun SectionTitle(text: String) {
    Text(text = text, style = MaterialTheme.typography.headlineSmall)
}
```

## Exceção: ajuste pontual derivado de um estilo do tema

```kotlin
// Não dispara finding — deriva de MaterialTheme.typography via .copy(...)
Text(
    text = price,
    style = MaterialTheme.typography.titleMedium.copy(fontSize = 20.sp),
)
```

## Exceção: `fontWeight` isolado

```kotlin
// Não dispara finding — ajuste pontual comum, sem fontSize/fontFamily inline
Text(text = label, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
```
