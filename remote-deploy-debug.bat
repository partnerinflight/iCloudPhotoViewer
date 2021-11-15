ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "sudo pkill -f python3"
ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "sudo rm -fR /home/pi/iCloudPhotoViewer/src"
ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "mkdir /home/pi/iCloudPhotoViewer/src"
scp  -i f:\adobe\photoframe\id_rsa -C -r src\ pi@192.168.1.6:/home/pi/iCloudPhotoViewer
ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "cd iCloudPhotoViewer/src; nohup sudo debugpy-run -p :5678 iCloudPhotoViewer.py > /dev/null & "
