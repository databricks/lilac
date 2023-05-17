import '@testing-library/jest-dom';
import {render, screen} from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import type {JSONSchema7} from 'json-schema';
import type {JSONError} from 'json-schema-library';
import html from 'svelte-htm';
import {get, writable} from 'svelte/store';
import JSONSchemaForm from './JSONSchemaForm.svelte';

describe('JSONSchemaForm', () => {
  it('should render text inputs with default text', async () => {
    const value = writable({});
    const schema: JSONSchema7 = {
      type: 'object',
      properties: {
        text: {
          type: 'string'
        }
      }
    };

    render(html`<${JSONSchemaForm} schema=${schema} bind:value=${value} />`);

    const input = screen.getByRole('textbox');
    expect(input).toBeInTheDocument();

    await userEvent.type(input, 'some text');

    expect(get(value)).toEqual({
      text: 'some text'
    });

    await userEvent.clear(input);

    expect(get(value)).toEqual({
      text: undefined
    });
  });

  it('should render arrays and objects', async () => {
    const value = writable({});
    const schema: JSONSchema7 = {
      type: 'object',
      properties: {
        array: {
          type: 'array',
          items: {$ref: '#/definitions/Array'}
        }
      },
      definitions: {
        Array: {
          type: 'object',
          properties: {
            name: {title: 'Name', type: 'string'},
            subdir: {title: 'Subdir', default: '', type: 'string'},
            path_suffix: {title: 'Path Suffix', default: 'suffix', type: 'string'}
          },
          required: ['name']
        }
      }
    };

    render(html`<${JSONSchemaForm} schema=${schema} bind:value=${value} />`);

    const addButton = screen.getByRole('button', {name: /add/i});
    expect(addButton).toBeInTheDocument();

    expect(get(value)).toEqual({});
    await userEvent.click(addButton);
    await userEvent.click(addButton);

    // Creates an object with default values
    expect(get(value)).toEqual({
      array: [
        {
          name: undefined,
          path_suffix: 'suffix',
          subdir: undefined
        },
        {
          name: undefined,
          path_suffix: 'suffix',
          subdir: undefined
        }
      ]
    });

    const nameInput = screen.getAllByRole('textbox', {name: /name/i});
    await userEvent.type(nameInput[0], 'some name');

    expect(get(value)).toEqual({
      array: [
        {
          name: 'some name',
          path_suffix: 'suffix',
          subdir: undefined
        },
        {
          name: undefined,
          path_suffix: 'suffix',
          subdir: undefined
        }
      ]
    });

    const removeButton = screen.getAllByRole('button', {name: /remove/i});
    await userEvent.click(removeButton[0]);

    expect(get(value)).toEqual({
      array: [
        {
          name: undefined,
          path_suffix: 'suffix',
          subdir: undefined
        }
      ]
    });
  });

  it('should validate the form', async () => {
    const value = writable({});
    const errors = writable<JSONError[]>([]);
    const schema: JSONSchema7 = {
      type: 'object',
      properties: {
        required_text: {
          title: 'Required Text',
          type: 'string'
        },
        optional_text: {
          title: 'Optional Text',
          type: 'string'
        }
      },
      required: ['required_text']
    };

    render(
      html`<${JSONSchemaForm}
        schema=${schema}
        bind:value=${value}
        bind:validationErrors=${errors}
      />`
    );

    const requiredInput = screen.getByRole('textbox', {name: 'Required Text *'});
    const optionalInput = screen.getByRole('textbox', {name: 'Optional Text'});

    const validationText = screen.getByText('Value is required');
    expect(validationText).toBeInTheDocument();

    expect(requiredInput).toHaveAttribute('aria-invalid', 'true');
    expect(optionalInput).not.toHaveAttribute('aria-invalid');

    expect(get(errors)[0]?.code).toEqual('required-property-error');

    await userEvent.type(requiredInput, 'some text');

    expect(get(errors)).toEqual([]);
    expect(requiredInput).not.toHaveAttribute('aria-invalid');
  });
});
