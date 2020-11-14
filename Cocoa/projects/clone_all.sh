cd $ROOTDIR/projects

URLS="git@github.com:CosmoLike/cocoa_des_y3.git
      git@github.com:CosmoLike/cocoa_desxplanck.git"

for NAME in $URLS; do
  git clone $NAME
done

# take the cocoa_ out of the dir names
for DIR in $(find . -mindepth 1 -maxdepth 1 -type d); do
    mv "${DIR}" $(echo "${DIR}" | sed -E 's@cocoa_@@') 2> /dev/null
done

cd $ROOTDIR