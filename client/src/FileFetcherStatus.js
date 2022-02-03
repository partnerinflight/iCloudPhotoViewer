import React, { useState, useEffect, useCallback } from 'react';
import Gallery from 'react-photo-gallery';
import Thumbnail from './Thumbnail';

function FileFetcherStatus(props) {
    const [ haveData, setHaveData ] = useState(false);
    const [ status, setStatus ] = useState([]);
    const [ album, setAlbum ] = useState([]);
    const [ numPhotos, setNumPhotos ] = useState(0);
    const [ numPhotosFetched, setNumPhotosFetched ] = useState(0);
    const [ cacheUsePercent, setCacheUsePercent ] = useState(0);
    const [ screenCommandsEnabled, setScreenCommandsEnabled ] = useState(true);
    const [ displayedPhotosList, setDisplayedPhotosList ] = useState([]);

    useEffect(() => {
        const interval = setInterval(async () => {
            const response = await fetch('/api/downloader_status');
            const json = await response.json();
            setStatus(json.status);
            setAlbum(json.album);
            setNumPhotos(json.numPhotos);
            setNumPhotosFetched(json.numPhotosProcessed);
            setCacheUsePercent(json.cacheUsePercent);
            setHaveData(true);

            const listResponse = await fetch('/api/displayed_list');
            const listJson = await listResponse.json();
            console.log(listJson);
            setDisplayedPhotosList(listJson)
        }, 5000);
        return () => clearInterval(interval);
    }, []);

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

    function renderStatus() {
        return (
        <div>           
            <div>{status}</div>
            <div>{`Album is: ${album}`}</div>
            <div>{`Fetched ${numPhotosFetched} photos, ${numPhotos} left`}</div>
            <div>{`Cache use: ${cacheUsePercent}%`}</div>
            <button disabled={!screenCommandsEnabled} onClick={() => sendScreenCommand("on")}>Screen On</button>
            <button disabled={!screenCommandsEnabled} onClick={() => sendScreenCommand("off")}>Screen Off</button>
        </div>)
    }

    function handleDelete(photo) {
        let photoName = photo.split('/').pop();
        console.log(`Deleting ${photoName}`);
        fetch('/api/delete_photo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 'photo': photoName })
        });
    }

    const imageRenderer = ({ index, left, top, key, photo }) => 
        (<Thumbnail photo={photo} left={left} top={top} handleClick={() => handleDelete(key)} />);
    
    return (  
        <div>
        { haveData ? renderStatus() : <div>Loading...</div> }
        { displayedPhotosList.length > 0 ? 
            <Gallery photos={displayedPhotosList.map(p => { return { src: `/media/${p}` }})} 
                renderImage={imageRenderer} style={{margin: "20px"}} /> :
           <div>No photos to display</div> }
        </div>
    )
}

export default FileFetcherStatus;