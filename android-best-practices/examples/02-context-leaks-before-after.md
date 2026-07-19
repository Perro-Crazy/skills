# Vazamento de Context/View e ViewBinding não limpo

## Antes

```kotlin
object AppState {
    var currentActivity: Activity? = null   // atualizado em onResume/onPause
}

class DetailFragment : Fragment() {
    private var _binding: FragmentDetailBinding? = null
    val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View {
        _binding = FragmentDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    inner class RefreshHandler : Handler(Looper.getMainLooper()) {
        override fun handleMessage(msg: Message) {
            binding.progressBar.isVisible = false
        }
    }
}
```

## Depois

```kotlin
object AppState {
    // nada de Activity aqui — se algo realmente precisa saber "há uma tela em primeiro
    // plano", exponha um Boolean/enum de estado, não a instância inteira.
    var hasForegroundActivity: Boolean = false
}

class DetailFragment : Fragment() {
    private var _binding: FragmentDetailBinding? = null
    val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View {
        _binding = FragmentDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onDestroyView() {
        super.onDestroyView()
        refreshHandler.removeCallbacksAndMessages(null)
        _binding = null
    }

    private val refreshHandler = RefreshHandler(WeakReference(this))

    private class RefreshHandler(
        private val fragmentRef: WeakReference<DetailFragment>,
    ) : Handler(Looper.getMainLooper()) {
        override fun handleMessage(msg: Message) {
            fragmentRef.get()?.binding?.progressBar?.isVisible = false
        }
    }
}
```

## Por quê

`AppState.currentActivity` foi trocado por um `Boolean` — nenhum lugar do app precisa da
instância inteira da Activity, só de saber que existe uma em primeiro plano, então a
troca elimina o vazamento sem perder a funcionalidade. `RefreshHandler` deixou de ser
`inner class` (que reteria o Fragment implicitamente) e passou a receber uma
`WeakReference<DetailFragment>` explícita — mensagens pendentes na fila não seguram mais
o Fragment vivo. `onDestroyView()` agora limpa mensagens pendentes do Handler e zera
`_binding`, liberando a view hierarchy antiga assim que ela é destruída, mesmo que a
instância do Fragment sobreviva num back stack.
