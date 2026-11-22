{
  description = "Environment for laboratory work 3: RAG over a PDF document";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (ps: [
            ps.jupyter
            ps.langchain
            ps."langchain-community"
            ps."langchain-ollama"
            ps."langchain-text-splitters"
            ps.pypdf
            ps.requests
          ]);
        in {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.ollama
              pkgs."poppler-utils"
            ];
          };
        });
    };
}
