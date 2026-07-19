# Strings/cores hardcoded e println em vez de Log

## Antes

```kotlin
class CheckoutActivity : AppCompatActivity() {
    fun onPaymentFailed() {
        println("Pagamento falhou, exibindo aviso ao usuário")
        Toast.makeText(this, "Não foi possível processar o pagamento", Toast.LENGTH_LONG).show()
        binding.statusDot.setBackgroundColor(Color.parseColor("#FFCC0000"))
    }
}
```

## Depois

```xml
<!-- res/values/strings.xml -->
<string name="checkout_payment_failed">Não foi possível processar o pagamento</string>
```

```xml
<!-- res/values/colors.xml -->
<color name="status_error">#FFCC0000</color>
```

```kotlin
class CheckoutActivity : AppCompatActivity() {
    fun onPaymentFailed() {
        Log.w(TAG, "Pagamento falhou, exibindo aviso ao usuário")
        Toast.makeText(this, getString(R.string.checkout_payment_failed), Toast.LENGTH_LONG).show()
        binding.statusDot.setBackgroundColor(ContextCompat.getColor(this, R.color.status_error))
    }

    companion object {
        private const val TAG = "CheckoutActivity"
    }
}
```

## Por quê

A string exibida ao usuário saiu do código-fonte para `strings.xml`, tornando o app
localizável sem editar Kotlin; a cor hex saiu para `colors.xml`, reaproveitável em
qualquer outro lugar que precise da mesma cor de erro (e trocável de uma vez se o
design system mudar o tom de vermelho); e `println` virou `Log.w` com uma `TAG`
consistente, visível no logcat filtrado por tag em vez de desaparecer no stdout do
processo.
