pylint --fail-under=9 anydex/test/wallet/*.py anydex/wallet/*.py || pylint-exit -efail $?
if [ $? -ne 0 ]; then
  echo "Python returned warning, error or refactor code." >&2
  exit 1
fi
