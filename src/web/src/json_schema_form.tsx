import {SlDetails, SlInput} from '@shoelace-style/shoelace/dist/react';
import {JSONSchema7} from 'json-schema';
import * as React from 'react';
import {ReactMarkdown} from 'react-markdown/lib/react-markdown';
import styles from './json_schema_form.module.css';

export interface JSONSchemaFormProps {
  schema: JSONSchema7;
  ignoreProperties: string[];
  onFormData: (formData: {[key: string]: string}) => void;
}

export const JSONSchemaForm = ({
  schema,
  ignoreProperties,
  onFormData,
}: JSONSchemaFormProps): JSX.Element => {
  const [formData, setFormData] = React.useState<{[key: string]: string}>({});
  const descriptionMarkdown = `### ${schema.description}`;

  // Call the parent when the form data changes.
  React.useEffect(() => onFormData(formData), [formData]);

  return (
    <div>
      <div className={styles.markdown_container}>
        <ReactMarkdown>{descriptionMarkdown}</ReactMarkdown>
      </div>
      {Object.entries(schema.properties || {}).map(([name, field]: [string, JSONSchema7]) => {
        if (ignoreProperties.includes(name)) {
          return <></>;
        }
        const isRequired = schema.required?.includes(name);
        const input = (
          <SlInput
            value={formData[name] || ''}
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
        const inputDetails = isRequired ? (
          input
        ) : (
          <SlDetails className={styles.optional_details} summary={name}>
            {input}
          </SlDetails>
        );

        return (
          <div key={name} className="mt-4">
            {inputDetails}
          </div>
        );
      })}
    </div>
  );
};
