import React, { useState, useEffect } from 'react';
import { ListGroup, ListGroupItem, Button } from 'reactstrap';

function MfaDeviceChoice(props) {
    const [ devices, setDevices ] = useState([]);

    useEffect(() => {
        const fetchDevices = async () => {
            const response = await fetch('/api/mfa_device_choice');
            const json = await response.json();
            console.log(json);
            setDevices(json);
        };

        fetchDevices();
    }, []);

    const handleClick = async (device) => {
        const response = await fetch('/api/mfa_device_choice', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device: device.deviceId
            })
        });
        const json = await response.json();
        props.setStatus(json['status']);
    };
    
    return (
        <ListGroup>
            {devices.map(device => (
                <ListGroupItem key={device.deviceId}>
                    <Button color="primary" onClick={() => handleClick(device)}>
                        {`${device.deviceType}: ${device.phoneNumber}`}
                    </Button>
                </ListGroupItem>
            ))}
        </ListGroup>
    );
}

export default MfaDeviceChoice;