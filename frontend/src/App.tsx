import { AppRouter } from './app/router'
import { ThemeProvider } from './app/theme/theme-provider'

function App() {
  return (
    <ThemeProvider>
      <AppRouter />
    </ThemeProvider>
  )
}

export default App
