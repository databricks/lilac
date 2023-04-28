import {
  SlCheckbox,
  SlDetails,
  SlIcon,
  SlIconButton,
  SlInput,
} from '@shoelace-style/shoelace/dist/react';
import {JSONSchema7, JSONSchema7Type, JSONSchema7TypeName} from 'json-schema';
import * as React from 'react';
import {ReactMarkdown} from 'react-markdown/lib/react-markdown';
import styles from './json_schema_form.module.css';

export const MultiInput = ({
  name,
  field,
  isRequired,
  showName,
  onFormData,
}: {
  name: string;
  field: JSONSchema7;
  showName: boolean;
  isRequired: boolean;
  onFormData: (formData: string[]) => void;
}): JSX.Element => {
  const [formData, setFormData] = React.useState<string[]>(['']);
  const [numInputs, setNumInputs] = React.useState<number>(1);
  [numInputs, setNumInputs];

  const updateFormData = (newFormData: string[]) => {
    setFormData(newFormData);

    // Only send the non-empty values to the parent.
    onFormData(newFormData.filter((x) => x != ''));
  };

  const inputs: JSX.Element[] = [];
  for (let i = 0; i < formData.length; i++) {
    inputs.push(
      <div className="mb-1 flex flex-row">
        <SlInput
          className="w-full"
          value={(formData[i] as string) || ''}
          type={'text'}
          required={isRequired}
          onSlChange={(e) => {
            const newFormData = [...formData];
            newFormData[i] = (e.target as HTMLInputElement).value;
            updateFormData(newFormData);
          }}
        >
          {/* Only show the delete button if there is more than one input. */}
          {isRequired && i === 0 && formData.length === 1 ? (
            <></>
          ) : (
            <div slot="suffix" className="mr-0">
              <SlIconButton
                name="X"
                slot="collapse-icon"
                onClick={() => updateFormData([...formData.slice(0, i), ...formData.slice(i + 1)])}
              />
            </div>
          )}
        </SlInput>
      </div>
    );
  }
  return (
    <div className="flex w-full flex-col">
      <div className="flex flex-row">
        <div className={styles.multi_form_field_name}>
          {showName ? `${name} ${isRequired ? '*' : ''}` : ''}
        </div>
        <div className="ml-auto">
          <SlIconButton
            name="plus"
            slot="expand-icon"
            onClick={() => updateFormData([...formData, ''])}
          />
        </div>
      </div>
      {inputs}
      <div className={styles.multi_form_help_text}>{field.description}</div>
    </div>
  );
};

export interface JSONSchemaFormProps {
  schema: JSONSchema7;
  ignoreProperties: string[];
  onFormData: (formData: {[key: string]: JSONSchema7Type}) => void;
}
export const JSONSchemaForm = ({
  schema,
  ignoreProperties,
  onFormData,
}: JSONSchemaFormProps): JSX.Element => {
  const [formData, setFormData] = React.useState<{[key: string]: JSONSchema7Type}>({});
  const descriptionMarkdown = `### ${schema.description}`;

  // Call the parent when the form data changes.
  React.useEffect(() => onFormData(formData), [formData, onFormData]);

  return (
    <div className="font-light">
      <div className={styles.markdown_container}>
        <ReactMarkdown>{descriptionMarkdown}</ReactMarkdown>
      </div>
      {Object.entries(schema.properties || {}).map(([name, field]: [string, JSONSchema7]) => {
        if (ignoreProperties.includes(name) || field.type == null) {
          return <div key={name}></div>;
        }
        if (Array.isArray(field.type)) {
          console.warn(`Ignoring field name with multiple types: ${field.type}`);
          return <div key={name}></div>;
        }

        const isRequired = schema.required?.includes(name);
        let input: JSX.Element = <></>;
        if (field.type === 'boolean') {
          input = (
            <SlCheckbox
              checked={Boolean(formData[name])}
              className={styles.checkbox}
              onSlChange={(e) =>
                setFormData({
                  ...formData,
                  [name]: (e.target as HTMLInputElement).checked,
                })
              }
            >
              {field.description}
            </SlCheckbox>
          );
        } else if (
          (['string', 'integer', 'number'] as JSONSchema7TypeName[]).includes(field.type)
        ) {
          input = (
            <SlInput
              value={(formData[name] as string) || ''}
              label={isRequired ? name : ''}
              type={field.type === 'number' || field.type == 'integer' ? 'number' : 'text'}
              required={isRequired}
              help-text={field.description}
              onSlChange={(e) =>
                setFormData({
                  ...formData,
                  [name]: (e.target as HTMLInputElement).value,
                })
              }
            />
          );
        } else if (field.type === 'array') {
          input = (
            <MultiInput
              name={name}
              field={field}
              isRequired={isRequired || false}
              showName={isRequired || false}
              onFormData={(fieldValues) =>
                setFormData({
                  ...formData,
                  [name]: fieldValues,
                })
              }
            ></MultiInput>
          );
        }
        const inputDetails = isRequired ? (
          input
        ) : (
          <SlDetails className={styles.optional_details} summary={name}>
            <SlIcon name="plus" slot="expand-icon" />
            <SlIcon name="dash" slot="collapse-icon" />
            {input}
          </SlDetails>
        );

        return (
          <div key={name} className="mt-4 w-96">
            {inputDetails}
          </div>
        );
      })}
    </div>
  );
};
