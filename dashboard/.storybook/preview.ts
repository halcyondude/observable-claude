import type { Preview } from '@storybook/sveltekit'
import '../src/app.css';

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
       color: /(background|color)$/i,
       date: /Date$/i,
      },
    },

    backgrounds: {
      default: 'cc-observer',
      values: [
        { name: 'cc-observer', value: '#0D1B2A' },
        { name: 'light', value: '#ffffff' },
      ],
    },

    a11y: {
      test: 'todo'
    }
  },
};

export default preview;