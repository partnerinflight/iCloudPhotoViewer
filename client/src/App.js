import './App.css';
import { Spinner } from 'reactstrap';
import React, { useState, useEffect } from 'react';
import MfaDeviceChoice from './MfaDeviceChoice';
import MfaCodeEntry from './MfaCodeEntry';
import Login from './Login';
import FileFetcherStatus from './FileFetcherStatus';

const statusMap = {
  "Querying": 0,
  "NotLoggedIn": 1,
  "NeedToSendMFACode": 2,
  "WaitingForMFACode": 3,
  "LoggedIn": 4,
}

function App() {
  const [ status, setStatus ] = useState(0);
  console.log(`In App, status is ${status}`)
  async function getStatus() {
    const response = await fetch('/api/status');
    const body = await response.json();
    return statusMap[body["status"]];
  }

  useEffect(() => {
    console.log("In useEffect");
    async function retrieveStatus() {
      setStatus(await getStatus());
    }
    retrieveStatus();
  }, []);

  return (
    <div className="App">
      {(status === 0 && <Spinner animation="border" variant="primary" />) ||
       (status === 1 && <Login setStatus={(status) => setStatus(statusMap[status])}/>) ||
       (status === 2 && <MfaDeviceChoice setStatus={(status) => setStatus(statusMap[status])}/>) ||
       (status === 3 && <MfaCodeEntry setStatus={(status) => setStatus(statusMap[status])}/>) ||
       (status === 4 && <FileFetcherStatus/>)}
    </div>
  );
}

export default App;
