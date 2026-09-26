import { Route, Routes } from 'react-router'

import { AppFrame } from './components/AppFrame'
import { HomePage } from './pages/HomePage'

export default function App() {
  return (
    <AppFrame>
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </AppFrame>
  )
}
