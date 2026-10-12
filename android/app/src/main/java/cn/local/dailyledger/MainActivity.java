package cn.local.dailyledger;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Collections;
import java.util.Date;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final String TAG = "DailyLedger";
    private static final String INDEX = "https://ledger.invalid/index.html";
    private static final int DOCUMENT_PICKER = 40;
    private static final Object PYTHON_LOCK = new Object();
    private static final Object LOG_LOCK = new Object();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private WebView webView;
    private TextView nativeError;
    private TextView documentStatus;
    private boolean pageReady;
    private boolean backInProgress;
    private OnBackInvokedCallback backCallback;
    private volatile DocumentState document;

    // Retained for an in-flight picker/worker. No Activity or WebView is used by the worker.
    private static final class DocumentState {
        String action;
        String payload;
        volatile String phase = "picker";
        String result;
        MainActivity owner;
        boolean delivering;
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.rgb(247, 247, 242));
        nativeError = new TextView(this);
        nativeError.setTextColor(Color.rgb(137, 24, 24));
        nativeError.setTextSize(14);
        nativeError.setPadding(16, 12, 16, 12);
        nativeError.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_ASSERTIVE);
        nativeError.setVisibility(View.GONE);
        layout.addView(nativeError);
        documentStatus = new TextView(this);
        documentStatus.setTextSize(14);
        documentStatus.setPadding(16, 10, 16, 10);
        documentStatus.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        documentStatus.setVisibility(View.GONE);
        layout.addView(documentStatus);
        webView = new WebView(this);
        layout.addView(webView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(layout);
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
        }
        layout.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
                                | WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        layout.requestApplyInsets();
        configureWebView();
        if (Build.VERSION.SDK_INT >= 33) {
            backCallback = this::handleBack;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, backCallback);
        }

        document = (DocumentState) getLastNonConfigurationInstance();
        if (document == null && savedInstanceState != null
                && savedInstanceState.containsKey("document.action")) {
            document = new DocumentState();
            document.action = savedInstanceState.getString("document.action");
            document.payload = savedInstanceState.getString("document.payload");
            document.phase = savedInstanceState.getString("document.phase");
            document.result = savedInstanceState.getString("document.result");
            if ("working".equals(document.phase)) {
                IllegalStateException error = new IllegalStateException(
                        "系统在文件处理过程中结束了应用，结果未确认。请检查当前账本和目标文件；不会自动重复操作。");
                recordError(getApplicationContext(), "document process interrupted: " + document.action, error);
                document.result = failure(document.action, error);
                document.phase = "result";
            }
        }
        if (document != null) {
            document.owner = this;
            showDocumentState();
        }
        webView.loadUrl(INDEX);
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true); // Local form drafts only; no server.
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setBlockNetworkLoads(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setGeolocationEnabled(false);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        webView.addJavascriptInterface(new LedgerBridge(), "AndroidLedger");
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (isTrustedPage(request.getUrl().toString())) return false;
                reportError("禁止离开本地记账页面", new SecurityException(request.getUrl().toString()));
                return true;
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                String name;
                String mime;
                if ("GET".equals(request.getMethod()) && INDEX.equals(url)) {
                    name = "index.html";
                    mime = "text/html";
                } else if ("GET".equals(request.getMethod()) && "https://ledger.invalid/style.css".equals(url)) {
                    name = "style.css";
                    mime = "text/css";
                } else if ("GET".equals(request.getMethod()) && "https://ledger.invalid/app.js".equals(url)) {
                    name = "app.js";
                    mime = "text/javascript";
                } else {
                    reportError("已阻止未授权资源", new SecurityException(request.getMethod() + " " + url));
                    return blockedResponse();
                }
                try {
                    java.util.Map<String, String> headers = new java.util.HashMap<>();
                    headers.put("Cache-Control", "no-store");
                    headers.put("X-Content-Type-Options", "nosniff");
                    headers.put("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                            + "style-src 'self' 'unsafe-inline'; img-src data:; connect-src 'none'; "
                            + "frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'");
                    return new WebResourceResponse(mime, "UTF-8", 200, "OK", headers,
                            getAssets().open(name));
                } catch (IOException error) {
                    reportError("本地页面资源读取失败：" + name, error);
                    return new WebResourceResponse("text/plain", "UTF-8", 500, "Asset read failed",
                            Collections.emptyMap(), new ByteArrayInputStream(
                                    error.toString().getBytes(StandardCharsets.UTF_8)));
                }
            }

            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                pageReady = false;
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                reportError("页面加载失败", new IOException(request.getUrl() + ": " + error.getDescription()));
            }

            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                reportError("已拒绝非本地安全连接", new SecurityException(error.toString()));
            }

            @android.annotation.TargetApi(26)
            @Override public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                pageReady = false;
                view.removeJavascriptInterface("AndroidLedger");
                ((LinearLayout) view.getParent()).removeView(view);
                view.destroy();
                webView = null;
                reportError("页面渲染进程已结束，请退出并重新打开应用；已保存的账本不受影响",
                        new IllegalStateException("WebView renderer gone, didCrash=" + detail.didCrash()));
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR) {
                    reportError("界面脚本错误", new IllegalStateException(message.sourceId() + ":"
                            + message.lineNumber() + " " + message.message()));
                }
                return true;
            }

            @Override public void onPermissionRequest(PermissionRequest request) {
                request.deny();
                reportError("页面权限请求已拒绝", new SecurityException(
                        java.util.Arrays.toString(request.getResources())));
            }
        });
    }

    private static WebResourceResponse blockedResponse() {
        return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
                Collections.emptyMap(), new ByteArrayInputStream("Forbidden".getBytes(StandardCharsets.UTF_8)));
    }

    private static boolean isTrustedPage(String url) {
        if (url == null) return false;
        int fragment = url.indexOf('#');
        return INDEX.equals(fragment < 0 ? url : url.substring(0, fragment));
    }

    private final class LedgerBridge {
        @JavascriptInterface public String request(String requestJson) {
            try {
                synchronized (PYTHON_LOCK) {
                    DocumentState pending = document;
                    if (pending != null && "restore".equals(pending.action) && !"result".equals(pending.phase)) {
                        throw new IllegalStateException("恢复操作进行中，请先完成或取消文件选择；期间不能访问或修改账本。");
                    }
                    return pythonCall(getApplicationContext(), "handle", requestJson);
                }
            } catch (Exception error) {
                reportError("账本请求失败", error);
                return failure(null, error);
            }
        }

        @JavascriptInterface public void ready() {
            MAIN.post(() -> {
                if (webView == null || !isTrustedPage(webView.getUrl())) {
                    reportError("页面来源校验失败", new SecurityException("Untrusted bridge ready"));
                    return;
                }
                pageReady = true;
                showDocumentState();
                deliverDocumentResult();
            });
        }

        @JavascriptInterface public boolean documentsPending() {
            return document != null;
        }

        @JavascriptInterface public void documents(String requestJson) {
            MAIN.post(() -> beginDocument(requestJson));
        }
    }

    private void beginDocument(String requestJson) {
        String action = null;
        DocumentState started = null;
        try {
            JSONObject request = new JSONObject(requestJson);
            action = request.getString("action");
            JSONObject payload = request.getJSONObject("payload");
            if (!action.equals("backup") && !action.equals("restore")
                    && !action.equals("csv") && !action.equals("logs")) {
                throw new IllegalArgumentException("未知文件操作：" + action);
            }
            if (document != null) throw new IllegalStateException("已有文件操作进行中，请先完成或取消系统文件选择。");
            started = new DocumentState();
            started.action = action;
            started.payload = payload.toString();
            started.owner = this;
            document = started;
            showDocumentState();
            Intent intent = new Intent(action.equals("restore")
                    ? Intent.ACTION_OPEN_DOCUMENT : Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType(action.equals("csv") ? "text/csv" : action.equals("logs") ? "text/plain" : "application/octet-stream");
            // Backup providers use inconsistent SQLite MIME types: the user selects one explicit file.
            if (action.equals("restore")) intent.setType("*/*");
            else intent.putExtra(Intent.EXTRA_TITLE, "日常记账_" + action + "_"
                    + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.ROOT).format(new Date())
                    + (action.equals("csv") ? ".csv" : action.equals("logs") ? ".log" : ".sqlite3"));
            startActivityForResult(intent, DOCUMENT_PICKER);
        } catch (Exception error) {
            reportError("文件操作启动失败", error);
            if (started != null) {
                started.result = failure(action, error);
                started.phase = "result";
                deliverDocumentResult();
            } else {
                deliverImmediateResult(failure(action, error));
            }
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != DOCUMENT_PICKER) return;
        if (document == null || !document.phase.equals("picker")) {
            reportError("文件选择结果没有对应操作", new IllegalStateException("Unexpected document result"));
            return;
        }
        if (resultCode == RESULT_CANCELED) {
            document.result = "{\"cancelled\":true,\"action\":" + JSONObject.quote(document.action) + "}";
            document.phase = "result";
            deliverDocumentResult();
            return;
        }
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            IllegalStateException error = new IllegalStateException("系统文件选择未返回有效文件 URI，结果码：" + resultCode);
            reportError("文件选择失败", error);
            document.result = failure(document.action, error);
            document.phase = "result";
            deliverDocumentResult();
            return;
        }
        Uri uri = data.getData();
        if (!"content".equals(uri.getScheme())) {
            SecurityException error = new SecurityException("仅接受系统文档提供者的 content URI：" + uri);
            reportError("无效文件来源", error);
            document.result = failure(document.action, error);
            document.phase = "result";
            deliverDocumentResult();
            return;
        }
        DocumentState work = document;
        Context context = getApplicationContext();
        work.phase = "working";
        showDocumentState();
        new Thread(() -> {
            String result;
            try {
                result = performDocument(context, work.action, work.payload, uri);
            } catch (Exception error) {
                recordError(context, "document transfer: " + work.action + " uri=" + uri, error);
                result = failure(work.action, error);
            }
            String completed = result;
            MAIN.post(() -> {
                work.result = completed;
                work.phase = "result";
                if (work.owner != null) work.owner.deliverDocumentResult();
            });
        }, "ledger-document").start();
    }

    private static String performDocument(Context context, String action, String payload, Uri uri)
            throws IOException, JSONException {
        File temporary = File.createTempFile("document-", ".tmp", context.getCacheDir());
        JSONObject response;
        Exception operationError = null;
        String cleanupWarning = null;
        try {
            if (action.equals("restore")) {
                try (InputStream source = context.getContentResolver().openInputStream(uri);
                     OutputStream target = new FileOutputStream(temporary)) {
                    if (source == null) throw new IOException("文档提供者未能打开所选文件");
                    copy(source, target);
                }
                response = new JSONObject(pythonCall(context, "restore_file", temporary.getAbsolutePath()));
            } else {
                response = new JSONObject(pythonCall(context, "export_file", action, payload, temporary.getAbsolutePath()));
                if (response.getBoolean("ok")) {
                    try (InputStream source = new FileInputStream(temporary);
                         OutputStream target = context.getContentResolver().openOutputStream(uri, "wt")) {
                        if (target == null) throw new IOException("文档提供者未能打开导出文件");
                        copy(source, target);
                    }
                }
            }
            response.put("action", action);
            if (response.getBoolean("ok")) {
                response.put("message", action.equals("restore") ? "账本已恢复；原账本已保存到应用内 backups 目录。"
                        : "文件已导出到所选位置。");
            } else {
                // Preserve the Python error envelope. Never copy an ungenerated export.
                response.getJSONObject("error").getString("message");
            }
        } catch (IOException | JSONException | RuntimeException error) {
            operationError = error;
            throw error;
        } finally {
            if (!temporary.delete()) {
                IOException cleanupError = new IOException("私有临时文件清理失败：" + temporary.getAbsolutePath());
                recordError(context, "private temporary file cleanup", cleanupError);
                if (operationError != null) operationError.addSuppressed(cleanupError);
                else cleanupWarning = describeError(cleanupError);
            }
        }
        if (cleanupWarning != null) {
            if (response.getBoolean("ok")) {
                // The ledger/file operation has already committed: expose cleanup failure without claiming it failed.
                response.put("message", response.getString("message") + "\n" + cleanupWarning);
                response.put("warning", cleanupWarning);
            } else {
                JSONObject error = response.getJSONObject("error");
                error.put("message", error.getString("message") + "\n" + cleanupWarning);
            }
        }
        return response.toString();
    }

    private static void copy(InputStream source, OutputStream target) throws IOException {
        byte[] buffer = new byte[65536];
        int count;
        while ((count = source.read(buffer)) != -1) target.write(buffer, 0, count);
        target.flush();
    }

    private static String pythonCall(Context context, String function, Object... arguments) {
        synchronized (PYTHON_LOCK) {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(context));
            Object[] pythonArguments = new Object[arguments.length + 1];
            pythonArguments[0] = context.getFilesDir().getAbsolutePath();
            System.arraycopy(arguments, 0, pythonArguments, 1, arguments.length);
            return Python.getInstance().getModule("mobile_api").callAttr(function, pythonArguments).toString();
        }
    }

    private void showDocumentState() {
        documentStatus.setVisibility(document == null ? View.GONE : View.VISIBLE);
        if (document != null) documentStatus.setText(document.phase.equals("picker")
                ? "系统文件选择进行中；请完成或取消后再操作。"
                : document.phase.equals("working") ? "正在处理文件，请稍候。" : "文件结果等待页面确认。");
        if (pageReady && webView != null) webView.evaluateJavascript(
                "if(typeof window.onDocumentBusy==='function')window.onDocumentBusy(" + (document != null) + ");", null);
    }

    private void deliverDocumentResult() {
        showDocumentState();
        if (!pageReady || webView == null || document == null || document.result == null || document.delivering) return;
        DocumentState completed = document;
        completed.delivering = true;
        webView.evaluateJavascript("(function(){if(typeof window.onDocumentResult!=='function')return false;"
                + "window.onDocumentResult(" + completed.result + ");return true;})()", acknowledgement -> {
            completed.delivering = false;
            if (!"true".equals(acknowledgement)) {
                reportError("文件结果未能交给页面，操作状态仍保留", new IllegalStateException("Document callback: " + acknowledgement));
                return;
            }
            if (document == completed) {
                completed.owner = null;
                document = null;
                showDocumentState();
            }
        });
    }

    private void deliverImmediateResult(String result) {
        if (pageReady && webView != null) webView.evaluateJavascript(
                "if(typeof window.onDocumentResult==='function')window.onDocumentResult(" + result + ");", null);
    }

    private static String failure(String action, Exception error) {
        return "{\"ok\":false," + (action == null ? "" : "\"action\":" + JSONObject.quote(action) + ",")
                + "\"error\":{\"type\":" + JSONObject.quote(error.getClass().getSimpleName())
                + ",\"message\":" + JSONObject.quote(describeError(error)) + "}}";
    }

    private static String describeError(Exception error) {
        StringBuilder description = new StringBuilder(error.toString());
        for (Throwable additional : error.getSuppressed()) description.append("\n另有错误：").append(additional);
        return description.toString();
    }

    private void reportError(String message, Exception error) {
        recordError(getApplicationContext(), message, error);
        MAIN.post(() -> {
            if (!isDestroyed()) {
                nativeError.setText(message + "\n" + describeError(error));
                nativeError.setVisibility(View.VISIBLE);
            }
        });
    }

    private static void recordError(Context context, String message, Exception error) {
        Log.e(TAG, message, error);
        String event = new Date() + " " + message + "\n" + Log.getStackTraceString(error) + "\n";
        synchronized (LOG_LOCK) {
            try (FileOutputStream stream = new FileOutputStream(new File(context.getFilesDir(), "errors.log"), true)) {
                stream.write(event.getBytes(StandardCharsets.UTF_8));
            } catch (IOException logError) {
                Log.e(TAG, "Cannot write private errors.log", logError);
                // Logging failure must remain visible to the caller, not masquerade as a logged error.
                error.addSuppressed(logError);
            }
        }
    }

    @Override protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (document != null) {
            outState.putString("document.action", document.action);
            outState.putString("document.payload", document.payload);
            outState.putString("document.phase", document.phase);
            outState.putString("document.result", document.result);
        }
    }

    @Override public Object onRetainNonConfigurationInstance() { return document; }

    @Override public void onBackPressed() { handleBack(); }

    private void handleBack() {
        if (backInProgress) return;
        if (!pageReady || webView == null) {
            finish();
            return;
        }
        backInProgress = true;
        webView.evaluateJavascript("(function(){return typeof window.handleAndroidBack==='function'"
                + " ? window.handleAndroidBack() : false;})()", handled -> {
            backInProgress = false;
            if ("false".equals(handled)) finish();
            else if (!"true".equals(handled)) {
                reportError("返回操作未得到有效页面响应", new IllegalStateException("Back callback: " + handled));
            }
        });
    }

    @Override protected void onPause() {
        if (webView != null) webView.onPause();
        super.onPause();
    }

    @Override protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }

    @Override protected void onDestroy() {
        if (Build.VERSION.SDK_INT >= 33 && backCallback != null) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(backCallback);
        }
        if (document != null && document.owner == this) document.owner = null;
        if (webView != null) {
            webView.removeJavascriptInterface("AndroidLedger");
            ((LinearLayout) webView.getParent()).removeView(webView);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
