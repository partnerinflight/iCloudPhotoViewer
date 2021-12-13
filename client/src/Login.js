import React, { useState, useEffect } from 'react';
import { Input, Button } from 'reactstrap';

function Login(props) {
    const [ userName, setUserName ] = useState('');
    const [ password, setPassword ] = useState('');
    
    async function handleSubmit(userName, password) {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                userName,
                password
            })
        });
        const json = await response.json();
        props.setStatus(json['status']);
    }

    return (
        <div>
            <Input type="text" placeholder="User Name" value={userName} onChange={(e) => setUserName(e.target.value)} />
            <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <Button onClick={() => handleSubmit(userName, password)}>Log In</Button>
        </div>
    );
}

export default Login;