{ toybox }:
args:
derivation (
  {
    builder = toybox;
    args = [
      "sh"
      (builtins.toFile "builder.sh" ''
        set -eux -o pipefail
        if [[ -e "''${NIX_ATTRS_SH_FILE:-}" ]]; then
          source "$NIX_ATTRS_SH_FILE"
        fi
        eval "$buildCommand"
      '')
    ];
  }
  // args
)
