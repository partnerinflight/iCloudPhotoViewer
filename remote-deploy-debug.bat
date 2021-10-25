ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "sudo pkill -f python3"
ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "sudo rm -fR src/"
ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "mkdir src"
pscp  -i f:\adobe\photoframe\id_rsa -C -r src\ pi@192.168.1.6:/home/pi/iCloudPhotoViewer
ssh -i f:\adobe\photoframe\id_rsa pi@192.168.1.6 "cd iCloudPhotoViewer/src; sudo nohup python3 iCloudPhotoViewer.py debug > /dev/null & "
