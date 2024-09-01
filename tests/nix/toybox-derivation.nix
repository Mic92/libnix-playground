{ toybox }:
let
  mkDerivation = import ./mkDerivation.nix { inherit toybox; };
in
mkDerivation {
  name = "toybox-derivation";
  system = builtins.currentSystem;
  buildCommand = ''
    touch $out
  '';
}
