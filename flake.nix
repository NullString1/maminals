{
  description = "Python TTS and AI Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
          };
        };
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = [
            pkgs.uv
            pkgs.python310
            pkgs.espeak
            pkgs.ffmpeg
          ];
          LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib";
          UV_PYTHON_DOWNLOADS="never";
        };
      }
    );
}
