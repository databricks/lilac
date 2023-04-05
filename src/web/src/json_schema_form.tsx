import {SlInput} from '@shoelace-style/shoelace/dist/react';
import {JSONSchema7} from 'json-schema';
import * as React from 'react';
import {ReactMarkdown} from 'react-markdown/lib/react-markdown';

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
      <ReactMarkdown>{descriptionMarkdown}</ReactMarkdown>
      {Object.entries(schema.properties || {}).map(([name, field]: [string, JSONSchema7]) => {
        if (ignoreProperties.includes(name)) {
          return <></>;
        }
        return (
          <div key={name} className="mt-4">
            <SlInput
              value={formData[name] || ''}
              label={name}
              type={field.type === 'number' || field.type == 'integer' ? 'number' : 'text'}
              required={schema.required?.includes(name)}
              help-text={field.description}
              onSlChange={(e) =>
                setFormData({
                  ...formData,
                  [name]: (e.target as HTMLInputElement).value,
                })
              }
            />
          </div>
        );
      })}
    </div>
  );
};
