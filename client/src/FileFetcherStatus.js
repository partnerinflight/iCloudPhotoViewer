import React, { useState, useEffect } from 'react';

function FileFetcherStatus(props) {
    const [ status, setStatus ] = useState([]);
    const [ album, setAlbum ] = useState([]);
    const [ numPhotos, setNumPhotos ] = useState(0);
    const [ numPhotosFetched, setNumPhotosFetched ] = useState(0);
    useEffect(() => {
        setTimeout(async () => {
            const response = await fetch('/api/downloader_status');
            const json = await response.json();
            setStatus(json.status);
            setAlbum(json.album);
            setNumPhotos(json.numPhotos);
            setNumPhotosFetched(json.numPhotosFetched);
        }, 5000);
    });

    return (
        <div>
            <div>{status}</div>
            <div>{`Album is: ${album}`}</div>
            <div>{`Fetched ${numPhotosFetched} photos, ${numPhotos} left`}</div>
        </div>
    );
}

export default FileFetcherStatus;