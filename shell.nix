{ mkShell, python3, bashInteractive, nix, lib }:
mkShell {
  packages = [
    bashInteractive
    python3
  ];
  LIBNIX_PATH = "${lib.getLib nix}/lib";
}
