import React from 'react';
import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

const PaperMinimal: React.FC = () => {
  console.log('PaperMinimal component rendering');
  
  return (
    <div>
      <Title level={2}>Paper Reproduction (Minimal Test)</Title>
      <Card>
        <Paragraph>
          This is the most basic version of the paper reproduction page.
        </Paragraph>
        <Paragraph>
          ✅ If you can see this, React and Ant Design are working correctly.
        </Paragraph>
        <Paragraph>
          ✅ The component has no external dependencies or API calls.
        </Paragraph>
      </Card>
    </div>
  );
};

export default PaperMinimal;