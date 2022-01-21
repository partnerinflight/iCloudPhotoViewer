import React, { useState, useEffect } from 'react';

function FileFetcherStatus(props) {
    const [ status, setStatus ] = useState([]);
    const [ album, setAlbum ] = useState([]);
    const [ numPhotos, setNumPhotos ] = useState(0);
    const [ numPhotosFetched, setNumPhotosFetched ] = useState(0);
    const [ cacheUsePercent, setCacheUsePercent ] = useState(0);
    const [ screenCommandsEnabled, setScreenCommandsEnabled ] = useState(true);
    useEffect(() => {
        setTimeout(async () => {
            const response = await fetch('/api/downloader_status');
            const json = await response.json();
            setStatus(json.status);
            setAlbum(json.album);
            setNumPhotos(json.numPhotos);
            setNumPhotosFetched(json.numPhotosProcessed);
            setCacheUsePercent(json.cacheUsePercent);
        }, 5000);
    });

    async function sendScreenCommand(command) {
        setScreenCommandsEnabled(false);
        await fetch('/api/screen_control', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 'action': command })
        });
        setScreenCommandsEnabled(true);
    }

    return (
        <div>
            <div>{status}</div>
            <div>{`Album is: ${album}`}</div>
            <div>{`Fetched ${numPhotosFetched} photos, ${numPhotos} left`}</div>
            <div>{`Cache use: ${cacheUsePercent}%`}</div>
            <button disabled={!screenCommandsEnabled} onClick={() => sendScreenCommand("on")}>Screen On</button>
            <button disabled={!screenCommandsEnabled} onClick={() => sendScreenCommand("off")}>Screen Off</button>
        </div>
    );
}

export default FileFetcherStatus;