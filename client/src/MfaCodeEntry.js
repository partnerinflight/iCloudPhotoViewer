import React, { useState, useEffect } from 'react';
import { Input, Button } from 'reactstrap';

function MfaCodeEntry(props) {
    const [ code, setCode ] = useState('');

    async function handleSubmit(code) {
        const response = await fetch('/api/mfa_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 'code': code })
        });
        const json = await response.json();
        props.setStatus(json['status']);
    }

    return (
        <div>
            <Input placeholder="MFA code" value={code} onChange={(e) => setCode(e.target.value)} />
            <Button onClick={() => handleSubmit(code)}>Submit</Button>
        </div>
    );
}

export default MfaCodeEntry;