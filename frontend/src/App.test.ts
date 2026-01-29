import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import App from './App.vue'

describe('App', () => {
  it('renders properly', () => {
    // Given: A mounted App component
    const wrapper = mount(App)
    
    // When: The component is rendered
    // Then: It should display the title
    expect(wrapper.text()).toContain('SynonymSeeker')
  })
})