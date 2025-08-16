git add .
set /P name="commit message? "
git commit -m "%name%"
git push origin main