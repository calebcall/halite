// frontend/tests/FunctionInput.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

import { FunctionInput } from '@/features/run/function-input'

const SAMPLE_FUNCTIONS = [
  'cmd.run',
  'cmd.shell',
  'file.managed',
  'pkg.installed',
  'state.apply',
  'state.highstate',
  'test.ping',
  'test.succeed_without_changes',
]

function renderWithState(initial = '') {
  const onChange = vi.fn()
  const Wrapper = () => {
    const [v, setV] = React.useState(initial)
    return (
      <FunctionInput
        id="fun"
        value={v}
        onChange={(next) => {
          onChange(next)
          setV(next)
        }}
        functions={SAMPLE_FUNCTIONS}
      />
    )
  }
  const utils = render(<Wrapper />)
  return { ...utils, onChange }
}

describe('FunctionInput', () => {
  it('opens the dropdown on focus and shows all functions (capped)', async () => {
    const user = userEvent.setup()
    renderWithState()
    await user.click(screen.getByRole('combobox'))
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
    // All 8 are under the cap of 10
    expect(screen.getAllByRole('option')).toHaveLength(SAMPLE_FUNCTIONS.length)
    expect(screen.getByText('state.apply')).toBeInTheDocument()
  })

  it('filters as the user types', async () => {
    const user = userEvent.setup()
    renderWithState()
    await user.click(screen.getByRole('combobox'))
    await user.type(screen.getByRole('combobox'), 'state')
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(2) // state.apply, state.highstate
    expect(screen.queryByText('cmd.run')).not.toBeInTheDocument()
  })

  it('selects on click and closes the dropdown', async () => {
    const user = userEvent.setup()
    const { onChange } = renderWithState()
    await user.click(screen.getByRole('combobox'))
    await user.type(screen.getByRole('combobox'), 'highstate')
    await user.click(screen.getByText('state.highstate'))
    expect(onChange).toHaveBeenCalledWith('state.highstate')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    renderWithState()
    await user.click(screen.getByRole('combobox'))
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
