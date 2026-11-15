// Imprime une page HTML locale en PDF A4, sans ouvrir de fenêtre visible (WebKit de macOS).
// Usage : html2pdf entree.html sortie.pdf
import AppKit
import WebKit

let args = CommandLine.arguments
let entree = URL(fileURLWithPath: args[1]), sortie = URL(fileURLWithPath: args[2])
let app = NSApplication.shared
app.setActivationPolicy(.prohibited)

class Delegue: NSObject, WKNavigationDelegate {
    func webView(_ w: WKWebView, didFinish _: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            let info = NSPrintInfo()
            info.paperSize = NSSize(width: 595.28, height: 841.89)
            info.topMargin = 0; info.bottomMargin = 0; info.leftMargin = 0; info.rightMargin = 0
            info.horizontalPagination = .fit; info.verticalPagination = .automatic
            info.jobDisposition = .save
            info.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = sortie
            let op = w.printOperation(with: info)
            op.showsPrintPanel = false; op.showsProgressPanel = false
            op.view?.frame = w.bounds
            op.runModal(for: fenetre, delegate: nil, didRun: nil, contextInfo: nil)
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { exit(0) }
        }
    }
}
let fenetre = NSWindow(contentRect: NSRect(x: -10000, y: -10000, width: 794, height: 1123), styleMask: [.borderless], backing: .buffered, defer: false)
let vue = WKWebView(frame: fenetre.contentView!.bounds)
fenetre.contentView!.addSubview(vue)
let delegue = Delegue()
vue.navigationDelegate = delegue
vue.loadFileURL(entree, allowingReadAccessTo: entree.deletingLastPathComponent())
DispatchQueue.main.asyncAfter(deadline: .now() + 30) { exit(1) }
app.run()
