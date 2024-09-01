{
  mkShell,
  python3,
  mypy,
  bashInteractive,
  nix,
  lib,
  # test dependencies
  toybox,
  pytest-asyncio,
  pytest,
  stdenv,
  pkgsStatic,
}:
mkShell {
  packages = [
    bashInteractive
    python3
    pytest-asyncio
    pytest
    mypy
    # TODO: does a non-static toybox work on macOS anyway?
  ] ++ (if stdenv.isLinux then [ pkgsStatic.toybox ] else [ toybox ]);
  LIBNIX_PATH = "${lib.getLib nix}/lib";
}
