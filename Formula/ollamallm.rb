class Ollamallm < Formula
  include Language::Python::Virtualenv

  desc "Recommend Ollama models based on your Mac or GPU hardware"
  homepage "https://github.com/zhmcoder/ollamallm"
  url "https://github.com/zhmcoder/ollamallm/releases/download/v0.1.1/ollamallm-0.1.1.tar.gz"
  sha256 "d9c5fe8faf02880ba2b8b0adc3c9453dea18257bc6fc56be37075367ad119a80"
  license "MIT"
  version "0.1.1"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/ollamallm help")
    assert_match "ollamallm", output
    assert_match "查本机", output
  end
end
