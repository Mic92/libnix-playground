{
  description = "Development environment for this project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";

    nix.url = "github:NixOS/nix";
    nix.inputs.nixpkgs.follows = "nixpkgs";
    nix.inputs.flake-parts.follows = "flake-parts";
    nix.inputs.git-hooks-nix.follows = "";
    nix.inputs.nixpkgs-regression.follows = "";
    nix.inputs.nixpkgs-23-11.follows = "";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } ({ lib, ... }: {
      systems = lib.systems.flakeExposed;
      perSystem = { inputs', pkgs, ... }: {
        devShells.default = pkgs.callPackage ./shell.nix {
          nix = inputs'.nix.packages.nix;
        };
      };
    });
}
