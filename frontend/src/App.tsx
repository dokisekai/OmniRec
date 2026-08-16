import React, { useState, useEffect, useRef } from 'react';
import { 
  Brain, CloudUpload, Sparkles, Tags, Search, Layers, 
  User, Palette, Mountain, Heart, Crop, Boxes, Image as ImageIcon, 
  Zap, Cpu, Disc, Video, Music, UploadCloud, Info, Copy, Check, Clock, Radio, 
  Sliders, Type, Terminal, Database, Trash2, Play, RefreshCw, Code2, ExternalLink,
  BookOpen, Send, ChevronRight, CheckCircle2
} from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';

interface CategorizedTags {
  Subject?: string[];
  ColorStyle?: string[];
  Scene?: string[];
  Emotion?: string[];
  Composition?: string[];
  Entity?: string[];
}

interface IndexResultData {
  item_id: string;
  tenant_id?: string;
  media_type: string;
  file_path: string;
  md5: string;
  title: string;
  description?: string;
  tags?: string[];
  is_vectorized?: boolean;
  categorized_tags?: CategorizedTags;
  dominant_colors?: string[];
}

interface RecommendationItem {
  item_id: string;
  tenant_id?: string;
  title: string;
  media_type: string;
  score: number;
  is_vectorized?: boolean;
  explanation: string;
}

interface ModelStatusInfo {
  model_id: string;
  modality: string;
  tier: string;
  memory_gb: number;
  status: string;
}

export function App() {
  const [activeTab, setActiveTab] = useState<'studio' | 'search' | 'lab' | 'library' | 'docs'>('studio');

  // Studio State
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [activeMediaType, setActiveMediaType] = useState<'image' | 'video' | 'audio'>('image');
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stageText, setStageText] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const [bootStatus, setBootStatus] = useState('正在连接状态流...');
  const [copied, setCopied] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Execution Mode Selection
  const [executionMode, setExecutionMode] = useState<'full' | 'vlm_only' | 'fast_vector' | 'embedding_only'>('full');

  // Configurable Analysis Focus Dimensions & Custom Prompt
  const [focusDimensions, setFocusDimensions] = useState<string[]>([
    'Subject', 'ColorStyle', 'Scene', 'Emotion', 'Composition', 'Entity'
  ]);
  const [customPrompt, setCustomPrompt] = useState<string>('');

  // Results State
  const [indexResult, setIndexResult] = useState<IndexResultData | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);

  // Search Tab State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFilter, setSearchFilter] = useState<string>('all');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<RecommendationItem[]>([]);

  // Lab Tab State (Embedding & Direct Prompt Testing)
  const [labText, setLabText] = useState('');
  const [labVector, setLabVector] = useState<number[] | null>(null);
  const [labDim, setLabDim] = useState<number>(0);
  const [isEmbeddingLoading, setIsEmbeddingLoading] = useState(false);
  const [labPrompt, setLabPrompt] = useState('重点分析画面人物的穿搭风格、衣服材质与发型特征');
  const [labResult, setLabResult] = useState<any>(null);
  const [isLabAnalyzing, setIsLabAnalyzing] = useState(false);

  // Tenant Isolation State
  const [activeTenant, setActiveTenant] = useState<string>('default');

  // Library Tab State
  const [libraryItems, setLibraryItems] = useState<IndexResultData[]>([]);
  const [isLibraryLoading, setIsLibraryLoading] = useState(false);

  // Developer Docs Tab State
  const [selectedApiEndpoint, setSelectedApiEndpoint] = useState<string>('upload');
  const [docTestResponse, setDocTestResponse] = useState<any>(null);
  const [docTestLoading, setDocTestLoading] = useState(false);
  const [copiedCurl, setCopiedCurl] = useState<string | null>(null);

  const [modelsList, setModelsList] = useState<ModelStatusInfo[]>([
    { modality: 'VLM', model_id: 'backend/models/mlx_model (Qwen3-VL-8B)', tier: 'L0 Permanent', memory_gb: 5.4, status: 'Active (Metal GPU 5.4GB)' },
    { modality: 'EMBEDDING', model_id: 'backend/models/qwen3_vl_embedding_8b', tier: 'L0 Permanent', memory_gb: 2.0, status: 'Active (2048d MRL 2.0GB)' },
    { modality: 'LLM', model_id: 'Bonsai-8B-MLX / Qwen3-8B', tier: 'L0 Permanent', memory_gb: 1.3, status: 'Active (Resident 1.3GB)' },
    { modality: 'RERANKER', model_id: 'backend/models/reranker_model (Qwen3-VL-Reranker)', tier: 'L0 Permanent', memory_gb: 2.0, status: 'Active (Resident 2.0GB)' },
    { modality: 'ASR', model_id: 'Whisper-large-v3 + Silero-VAD', tier: 'L0 Permanent', memory_gb: 0.7, status: 'Active (Resident 0.7GB)' },
    { modality: 'CLAP', model_id: 'backend/models/clap_model (LAION CLAP)', tier: 'L0 Permanent', memory_gb: 0.6, status: 'Active (Resident 0.6GB)' },
  ]);

  // Fetch real model status on boot
  useEffect(() => {
    fetch('/api/v1/models/status')
      .then(res => res.json())
      .then(data => {
        if (data.loaded_models) {
          const fetchedList: ModelStatusInfo[] = Object.keys(data.loaded_models).map(key => ({
            modality: key.toUpperCase(),
            model_id: data.loaded_models[key].model_id,
            tier: data.loaded_models[key].tier === 'L0' ? 'L0 Permanent' : 'L1 Hot Cache',
            memory_gb: data.loaded_models[key].memory_gb,
            status: 'Active (Resident)'
          }));
          setModelsList(fetchedList);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch library items when opening library tab (with tenant filter)
  const fetchLibrary = async (tenant = activeTenant) => {
    setIsLibraryLoading(true);
    try {
      const url = tenant && tenant !== 'all' ? `/api/v1/items?tenant_id=${encodeURIComponent(tenant)}` : '/api/v1/items';
      const res = await fetch(url);
      const data = await res.json();
      if (data.items) setLibraryItems(data.items);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLibraryLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'library') {
      fetchLibrary(activeTenant);
    }
  }, [activeTab, activeTenant]);

  // WebSocket: real-time indexing status
  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    let ws: WebSocket;
    let closed = false;
    const connect = () => {
      const wsHost = (window.location.port === '5173' || window.location.port === '5174')
        ? `${window.location.hostname}:8000`
        : window.location.host;
      ws = new WebSocket(`${proto}://${wsHost}/ws/progress`);
      wsRef.current = ws;
      ws.onopen = () => { setWsConnected(true); setBootStatus('状态流已连接，全模型常驻显存中'); };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          handleWsMessage(msg);
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        setWsConnected(false);
        if (!closed) setBootStatus('状态流重连中...');
        if (!closed) setTimeout(connect, 3000);
      };
      ws.onerror = () => { ws.close(); };
    };
    connect();
    return () => { closed = true; ws.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Polling fallback to guarantee UI updates when L2 background inference finishes
  useEffect(() => {
    if (!isUploading || !indexResult?.item_id) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/v1/items');
        const data = await res.json();
        if (data.items) {
          const item = data.items.find((it: any) => it.item_id === indexResult.item_id);
          if (item && item.metadata?.status === 'completed' && item.description && item.description.length > 50) {
            setIndexResult((prev) => ({
              ...(prev || {} as IndexResultData),
              description: item.description,
              tags: item.tags,
              categorized_tags: item.metadata?.categorized_tags || prev?.categorized_tags,
              dominant_colors: item.metadata?.dominant_colors || prev?.dominant_colors
            }) as IndexResultData);
            setStageText('✅ L2 VLM 深度多模态富文本与 6 维标签生成完成！');
            setProgress(100);
            setIsUploading(false);
            if (executionMode === 'full') fetchRecommendations(item.item_id);
            setTimeout(() => setProgress(0), 3000);
          }
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [isUploading, indexResult?.item_id, executionMode]);

  const handleWsMessage = (msg: any) => {
    switch (msg.type) {
      case 'connected':
        setWsConnected(true);
        setBootStatus(msg.message || '状态流已连接');
        break;
      case 'l1_start':
        setStageText(msg.message);
        setProgress(30);
        break;
      case 'l1_progress':
        setStageText(msg.message);
        setProgress(60);
        break;
      case 'l1_done':
        setStageText(msg.message || 'L1 快速特征已就绪...');
        setProgress(executionMode === 'fast_vector' || executionMode === 'embedding_only' ? 100 : 65);
        if (executionMode === 'fast_vector' || executionMode === 'embedding_only') {
          setIsUploading(false);
          setTimeout(() => setProgress(0), 2000);
        }
        if (msg.result) {
          setIndexResult((prev) => ({
            ...(prev || {} as IndexResultData),
            ...msg.result,
          }) as IndexResultData);
          if (msg.item_id && executionMode === 'full') fetchRecommendations(msg.item_id);
        }
        break;
      case 'l2_start':
        setStageText(msg.message || '正在调用 Apple Silicon GPU (Qwen3-VL-8B) 推理多模态富文本与 6 维标签...');
        setProgress(85);
        break;
      case 'l2_progress':
        setStageText(msg.message);
        setProgress(90);
        break;
      case 'l2_done':
      case 'l2_complete':
        setStageText(msg.message || '✅ L2 VLM 深度多模态富文本与 6 维标签生成完成！');
        setProgress(100);
        setIsUploading(false);
        if (msg.result) {
          setIndexResult((prev) => ({
            ...(prev || {} as IndexResultData),
            ...msg.result,
          }) as IndexResultData);
          if (msg.item_id && executionMode === 'full') fetchRecommendations(msg.item_id);
        }
        setTimeout(() => setProgress(0), 3000);
        break;
      case 'l2_error':
        setStageText(msg.message || '多模态分析异常');
        setIsUploading(false);
        setTimeout(() => setProgress(0), 3000);
        break;
      default:
        break;
    }
  };

  const detectMediaType = (filename: string, fileType?: string): 'image' | 'video' | 'audio' => {
    if (fileType?.startsWith('video/') || /\.(mp4|mov|avi|mkv|webm)$/i.test(filename)) return 'video';
    if (fileType?.startsWith('audio/') || /\.(wav|mp3|m4a|aac|flac|ogg)$/i.test(filename)) return 'audio';
    return 'image';
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setActiveMediaType(detectMediaType(selectedFile.name, selectedFile.type));
    }
  };

  const toggleDimension = (dim: string) => {
    setFocusDimensions(prev => 
      prev.includes(dim) ? prev.filter(d => d !== dim) : [...prev, dim]
    );
  };

  // Upload & Index
  const handleUpload = async () => {
    if (!file) {
      alert('请先选择或拖拽一个真实媒体文件！');
      return;
    }

    const mType = detectMediaType(file.name, file.type);
    setActiveMediaType(mType);
    setIsUploading(true);
    setProgress(20);
    setStageText(`正在以 [${executionMode}] 模式处理 ${mType} 文件...`);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('media_type', mType);
    formData.append('mode', executionMode);
    formData.append('tenant_id', activeTenant);
    formData.append('focus_dimensions', JSON.stringify(focusDimensions));
    if (customPrompt.trim()) {
      formData.append('custom_prompt', customPrompt.trim());
    }

    try {
      const res = await fetch('/api/v1/upload', {
        method: 'POST',
        body: formData
      });

      const data = await res.json();

      if (data.status === 'success' && data.index_result) {
        const rawRes = data.index_result;
        const normalizedRes: IndexResultData = {
          item_id: rawRes.item_id,
          tenant_id: rawRes.tenant_id || activeTenant,
          media_type: rawRes.media_type,
          file_path: rawRes.file_path,
          md5: rawRes.md5,
          title: rawRes.title || rawRes.file_path.split('/').pop() || '上传文件',
          description: rawRes.description,
          tags: rawRes.tags,
          is_vectorized: rawRes.is_vectorized !== false,
          categorized_tags: rawRes.categorized_tags || rawRes.metadata?.categorized_tags,
          dominant_colors: rawRes.dominant_colors || rawRes.metadata?.dominant_colors || ['#fdfdfd', '#ffffff']
        };
        setIndexResult(normalizedRes);

        if (executionMode === 'fast_vector' || executionMode === 'embedding_only') {
          setProgress(100);
          setIsUploading(false);
          setStageText(executionMode === 'fast_vector' ? '⚡ 快速向量提取完成 (<50ms)' : '🎯 2048 维向量嵌入生成完毕');
          setTimeout(() => setProgress(0), 2000);
        } else {
          setProgress(65);
          setStageText('正在按配置维度进行后台 GPU 深度推演...');
          if (executionMode === 'full') {
            fetchRecommendations(rawRes.item_id);
          }
        }
      }
    } catch (err) {
      setProgress(0);
      setStageText('上传解析出错，请检查网络');
      console.error(err);
    }
  };

  // Fetch Recommendations
  const fetchRecommendations = async (seedId: string) => {
    try {
      const res = await fetch('/api/v1/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: seedId,
          tenant_id: activeTenant,
          top_k: 4,
          only_vectorized: true
        })
      });
      const data = await res.json();
      if (data.recommendations && data.recommendations.length > 0) {
        setRecommendations(data.recommendations);
      } else {
        setRecommendations([]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Multimodal Search
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch('/api/v1/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_text: searchQuery,
          tenant_id: activeTenant,
          filter_media_type: searchFilter === 'all' ? null : searchFilter,
          only_vectorized: true,
          top_k: 8,
          enable_rerank: true,
          enable_explanation: true
        })
      });
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        setSearchResults(data.results.map((r: any) => ({
          item_id: r.item_id,
          tenant_id: r.tenant_id || activeTenant,
          title: r.title || r.file_path.split('/').pop(),
          media_type: r.media_type,
          score: r.score,
          is_vectorized: r.is_vectorized !== false,
          explanation: r.explanation || `匹配语义相关度 ${(r.score * 100).toFixed(1)}%`
        })));
      } else {
        setSearchResults([]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSearching(false);
    }
  };

  // Lab: Generate Vector Embedding
  const handleGenerateEmbedding = async () => {
    if (!labText.trim()) return;
    setIsEmbeddingLoading(true);
    try {
      const res = await fetch('/api/v1/embed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: labText })
      });
      const data = await res.json();
      if (data.full_vector) {
        setLabVector(data.full_vector);
        setLabDim(data.dim);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsEmbeddingLoading(false);
    }
  };

  // Lab: Direct VLM Prompt Analysis
  const handleDirectAnalyze = async () => {
    if (!file) {
      alert('请先在工作台或此处选择一个媒体文件！');
      return;
    }
    setIsLabAnalyzing(true);
    try {
      const res = await fetch('/api/v1/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: (file as any).path || `test_files/${file.name}`,
          media_type: detectMediaType(file.name, file.type),
          focus_dimensions: focusDimensions,
          custom_prompt: labPrompt
        })
      });
      const data = await res.json();
      setLabResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLabAnalyzing(false);
    }
  };

  // Library: Delete Item
  const handleDeleteItem = async (itemId: string) => {
    if (!confirm(`确定删除向量索引条目: ${itemId} 吗？`)) return;
    try {
      await fetch(`/api/v1/items/${itemId}`, { method: 'DELETE' });
      setLibraryItems(prev => prev.filter(it => it.item_id !== itemId));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCopyDescription = () => {
    if (indexResult?.description) {
      navigator.clipboard.writeText(indexResult.description);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCurl(id);
    setTimeout(() => setCopiedCurl(null), 2000);
  };

  const dimensionOptions = [
    { key: 'Subject', label: '主体与细节', icon: <User size={13} color="#6366f1" /> },
    { key: 'ColorStyle', label: '重点色彩与光影', icon: <Palette size={13} color="#ec4899" /> },
    { key: 'Scene', label: '场景与空间', icon: <Mountain size={13} color="#10b981" /> },
    { key: 'Emotion', label: '情绪与意境', icon: <Heart size={13} color="#f59e0b" /> },
    { key: 'Composition', label: '构图与视角', icon: <Crop size={13} color="#06b6d4" /> },
    { key: 'Entity', label: '实体与配件', icon: <Boxes size={13} color="#a855f7" /> },
    { key: 'OCR', label: '文字与标识', icon: <Type size={13} color="#3b82f6" /> },
  ];

  // Developer API Definitions
  const apiDefinitions = [
    {
      id: 'upload',
      title: '多模态文件上传与渐进式索引',
      method: 'POST',
      path: '/api/v1/upload',
      category: '特征提取与索引',
      description: '上传图片、视频或音频文件，指定任务模式（全流程/仅VLM/仅快速向量/仅嵌入），按需提取特征与分类标签。',
      contentType: 'multipart/form-data',
      params: [
        { name: 'file', type: 'UploadFile (Binary)', in: 'form', req: true, def: '-', desc: '媒体文件二进制数据（.jpg, .png, .mp4, .mov, .wav 等）' },
        { name: 'media_type', type: 'string', in: 'form', req: false, def: 'image', desc: "媒体类型枚举: 'image' | 'video' | 'audio'" },
        { name: 'mode', type: 'string', in: 'form', req: false, def: 'full', desc: "执行模式: 'full' (全流程) | 'vlm_only' (仅大模型解析) | 'fast_vector' (仅快速特征) | 'embedding_only' (仅2048维向量)" },
        { name: 'focus_dimensions', type: 'string (JSON array)', in: 'form', req: false, def: '["Subject",...]', desc: "大模型关注维度列表，如: ['Subject', 'ColorStyle', 'Scene', 'Emotion', 'Composition', 'Entity', 'OCR']" },
        { name: 'custom_prompt', type: 'string', in: 'form', req: false, def: "''", desc: "自定义自然语言关注重点指令，如: '重点分析人物服装与发型'" }
      ],
      curlSample: `curl -X POST http://localhost:8000/api/v1/upload \\
  -F "file=@test_files/beauty_1755438760705.jpeg" \\
  -F "media_type=image" \\
  -F "mode=full" \\
  -F 'focus_dimensions=["Subject","ColorStyle","Emotion"]' \\
  -F "custom_prompt=重点分析人物穿搭和发型以及画面粉色调"`,
      responseSample: `{
  "status": "success",
  "mode": "full",
  "saved_path": "/cache/uploads/1786814242_beauty.jpeg",
  "filename": "beauty.jpeg",
  "index_result": {
    "item_id": "item_18f289229f91",
    "media_type": "image",
    "title": "beauty.jpeg",
    "md5": "18f289229f9137e40fc519af8da3e50f",
    "dominant_colors": ["#f3d7df", "#8a5864"],
    "tags": ["人物肖像", "粉色柔和", "车内私密空间"]
  }
}`
    },
    {
      id: 'analyze',
      title: '纯大模型单次推演与特征解析',
      method: 'POST',
      path: '/api/v1/analyze',
      category: '大模型推演',
      description: '直接调用显存常驻的 Qwen3-VL-8B 或 Whisper/CLAP，执行纯推理并返回富文本描述、6维标签与2048维向量（不写入向量数据库）。',
      contentType: 'application/json',
      params: [
        { name: 'file_path', type: 'string', in: 'body', req: true, def: '-', desc: '服务器本地文件绝对或相对路径' },
        { name: 'media_type', type: 'string', in: 'body', req: false, def: 'image', desc: "媒体类型: 'image' | 'video' | 'audio'" },
        { name: 'focus_dimensions', type: 'List[string]', in: 'body', req: false, def: 'null', desc: '选定的分析维度数组' },
        { name: 'custom_prompt', type: 'string', in: 'body', req: false, def: 'null', desc: '用户自定义分析指令' }
      ],
      curlSample: `curl -X POST http://localhost:8000/api/v1/analyze \\
  -H "Content-Type: application/json" \\
  -d '{
    "file_path": "test_files/beauty_1755438760705.jpeg",
    "media_type": "image",
    "focus_dimensions": ["Subject", "ColorStyle", "Emotion"],
    "custom_prompt": "重点分析人物穿搭和发型以及画面粉色调"
  }'`,
      responseSample: `{
  "status": "success",
  "media_type": "image",
  "description": "照片主角是一位年轻女性，通过后视镜自拍，身着粉色针织短袖上衣...",
  "categorized_tags": {
    "Subject": ["人物肖像", "车辆交通"],
    "ColorStyle": ["粉色柔和"],
    "Scene": ["车内私密空间"],
    "Emotion": ["俏皮害羞"],
    "Composition": ["后视镜倒影"],
    "Entity": ["人像服饰", "汽车配件", "后视镜"]
  },
  "embedding_dim": 2048
}`
    },
    {
      id: 'embed',
      title: '2048 维跨模态稠密向量生成',
      method: 'POST',
      path: '/api/v1/embed',
      category: '向量嵌入',
      description: '生成 Qwen3-VL-Embedding 2048 维 MRL 稠密特征向量。支持传入纯文本或媒体文件路径。',
      contentType: 'application/json',
      params: [
        { name: 'text', type: 'string', in: 'body', req: false, def: 'null', desc: '待向量化的自然语言文本（与 file_path 二选一）' },
        { name: 'file_path', type: 'string', in: 'body', req: false, def: 'null', desc: '媒体文件本地路径（直接提取原生像素/声学特征向量）' },
        { name: 'media_type', type: 'string', in: 'body', req: false, def: 'image', desc: "文件模态: 'image' | 'video' | 'audio'" }
      ],
      curlSample: `curl -X POST http://localhost:8000/api/v1/embed \\
  -H "Content-Type: application/json" \\
  -d '{"text": "车内自拍 女性粉色短袖"}'`,
      responseSample: `{
  "status": "success",
  "type": "text",
  "dim": 2048,
  "vector_sample": [0.0124, -0.0451, 0.0892, -0.0031, 0.0415, -0.0211, 0.0654, 0.0112],
  "full_vector": [...]
}`
    },
    {
      id: 'search',
      title: '多模态联合检索 (RRF + Rerank)',
      method: 'POST',
      path: '/api/v1/search',
      category: '检索与推荐',
      description: '输入自然语言文本，在 2048 维密集向量空间中执行余弦召回与 Qwen3 跨模态重排。',
      contentType: 'application/json',
      params: [
        { name: 'query_text', type: 'string', in: 'body', req: true, def: '-', desc: '用户搜索文本描述' },
        { name: 'filter_media_type', type: 'string', in: 'body', req: false, def: 'null', desc: "过滤特定模态: 'image' | 'video' | 'audio' | null (全部)" },
        { name: 'top_k', type: 'integer', in: 'body', req: false, def: '10', desc: '返回最相关的条目数量' },
        { name: 'enable_rerank', type: 'boolean', in: 'body', req: false, def: 'true', desc: '是否启用 Qwen3-VL-Reranker 二次精排' },
        { name: 'enable_explanation', type: 'boolean', in: 'body', req: false, def: 'true', desc: '是否启用 LLM 生成语义匹配原因' }
      ],
      curlSample: `curl -X POST http://localhost:8000/api/v1/search \\
  -H "Content-Type: application/json" \\
  -d '{
    "query_text": "粉色上衣车内自拍",
    "filter_media_type": null,
    "top_k": 5,
    "enable_rerank": true
  }'`,
      responseSample: `{
  "query": "粉色上衣车内自拍",
  "total_hits": 1,
  "results": [
    {
      "item_id": "item_18f289229f91",
      "media_type": "image",
      "title": "beauty.jpeg",
      "score": 0.942,
      "explanation": "匹配特征：粉色短袖、车内后视镜自拍视角、高置信度语义相关。"
    }
  ]
}`
    },
    {
      id: 'recommend',
      title: 'Item-to-Item 深度相似推荐',
      method: 'POST',
      path: '/api/v1/recommend',
      category: '检索与推荐',
      description: '基于种子条目（seed item_id），利用双轨向量空间与 MMR 多样性重排，输出相似关联内容。',
      contentType: 'application/json',
      params: [
        { name: 'item_id', type: 'string', in: 'body', req: true, def: '-', desc: '种子条目的唯一 ID (如: item_18f289229f91)' },
        { name: 'top_k', type: 'integer', in: 'body', req: false, def: '4', desc: '推荐候选数量' },
        { name: 'enable_explanation', type: 'boolean', in: 'body', req: false, def: 'true', desc: '是否生成 AI 推荐原因' }
      ],
      curlSample: `curl -X POST http://localhost:8000/api/v1/recommend \\
  -H "Content-Type: application/json" \\
  -d '{"item_id": "item_18f289229f91", "top_k": 4}'`,
      responseSample: `{
  "seed_item_id": "item_18f289229f91",
  "recommendations": [
    {
      "item_id": "item_b46c7a70740d",
      "title": "sample_car.jpeg",
      "media_type": "image",
      "score": 0.887,
      "explanation": "场景均为车内私密空间，构图与色彩基调具有高度相似性。"
    }
  ]
}`
    },
    {
      id: 'status',
      title: '模型矩阵与常驻显存状态',
      method: 'GET',
      path: '/api/v1/models/status',
      category: '系统监控',
      description: '查询当前 GPU 上已常驻加载的模型（VLM、Embedding、LLM、Reranker、ASR、CLAP）及显存占用（12.0GB / 20.0GB）。',
      contentType: 'none',
      params: [],
      curlSample: `curl http://localhost:8000/api/v1/models/status`,
      responseSample: `{
  "memory_limit_gb": 20.0,
  "current_usage_gb": 12.0,
  "loaded_models": {
    "vlm": { "model_id": "backend/models/mlx_model", "tier": "L0", "memory_gb": 5.4 },
    "embedding": { "model_id": "backend/models/qwen3_vl_embedding_8b", "tier": "L0", "memory_gb": 2.0 },
    "reranker": { "model_id": "backend/models/reranker_model", "tier": "L0", "memory_gb": 2.0 },
    "llm": { "model_id": "bonsai-8b-mlx", "tier": "L0", "memory_gb": 1.3 },
    "asr": { "model_id": "Whisper-large-v3", "tier": "L0", "memory_gb": 0.7 },
    "clap": { "model_id": "backend/models/clap_model", "tier": "L0", "memory_gb": 0.6 }
  }
}`
    },
    {
      id: 'items',
      title: '全量向量索引条目库列表',
      method: 'GET',
      path: '/api/v1/items',
      category: '索引管理',
      description: '读取当前向量数据库中已建立索引的所有多模态文件与元数据。',
      contentType: 'none',
      params: [],
      curlSample: `curl http://localhost:8000/api/v1/items`,
      responseSample: `{
  "status": "success",
  "total": 3,
  "items": [
    {
      "item_id": "item_18f289229f91",
      "media_type": "image",
      "title": "beauty.jpeg",
      "tags": ["人物肖像", "粉色柔和"]
    }
  ]
}`
    },
    {
      id: 'delete_item',
      title: '删除指定向量条目',
      method: 'DELETE',
      path: '/api/v1/items/{item_id}',
      category: '索引管理',
      description: '根据 item_id 从向量数据库和缓存中移除该条目。',
      contentType: 'none',
      params: [
        { name: 'item_id', type: 'string', in: 'path', req: true, def: '-', desc: '要删除的条目 ID' }
      ],
      curlSample: `curl -X DELETE http://localhost:8000/api/v1/items/item_18f289229f91`,
      responseSample: `{
  "status": "success",
  "message": "Item item_18f289229f91 deleted."
}`
    },
    {
      id: 'ws',
      title: '实时推理与状态 WebSocket 推送流',
      method: 'WS',
      path: '/ws/progress',
      category: '实时通信',
      description: 'WebSocket 长连接，接收大模型 L1/L2 加载、推演进度与多模态解析结果实时推送。',
      contentType: 'WebSocket Frames',
      params: [],
      curlSample: `# 连接 WebSocket:
ws://localhost:8000/ws/progress`,
      responseSample: `{
  "type": "l2_done",
  "item_id": "item_18f289229f91",
  "message": "✅ L2 VLM 深度多模态富文本与 6 维标签生成完成！",
  "result": { ... }
}`
    }
  ];

  const handleRunDocTest = async (endpoint: any) => {
    setDocTestLoading(true);
    try {
      if (endpoint.id === 'status') {
        const res = await fetch('/api/v1/models/status');
        const data = await res.json();
        setDocTestResponse(data);
      } else if (endpoint.id === 'items') {
        const res = await fetch('/api/v1/items');
        const data = await res.json();
        setDocTestResponse(data);
      } else if (endpoint.id === 'embed') {
        const res = await fetch('/api/v1/embed', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: '车内自拍 女性粉色上衣' })
        });
        const data = await res.json();
        setDocTestResponse(data);
      } else if (endpoint.id === 'search') {
        const res = await fetch('/api/v1/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query_text: '粉色自拍', top_k: 3 })
        });
        const data = await res.json();
        setDocTestResponse(data);
      } else if (endpoint.id === 'analyze') {
        const res = await fetch('/api/v1/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_path: 'test_files/beauty_1755438760705.jpeg',
            media_type: 'image',
            focus_dimensions: ['Subject', 'ColorStyle'],
            custom_prompt: '在线接口测试：重点分析颜色与主体'
          })
        });
        const data = await res.json();
        setDocTestResponse(data);
      } else {
        setDocTestResponse({ message: `可直接使用左侧工作台或下方 cURL 命令测试 ${endpoint.path}` });
      }
    } catch (e: any) {
      setDocTestResponse({ error: e.message || '请求失败' });
    } finally {
      setDocTestLoading(false);
    }
  };

  const currentEndpoint = apiDefinitions.find(a => a.id === selectedApiEndpoint) || apiDefinitions[0];

  const renderStructuredDescription = () => {
    if (isUploading && !indexResult?.description) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 180, gap: '0.75rem', color: '#06b6d4' }}>
          <div className="animate-pulse-glow" style={{ width: 14, height: 14, borderRadius: '50%', background: '#06b6d4' }} />
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Apple Silicon GPU (Qwen3-VL-8B) 正在执行自定义多维推演...</span>
        </div>
      );
    }
    const desc = indexResult?.description;
    if (!desc) {
      return <div style={{ color: '#6b7280', fontSize: '0.82rem', padding: '1rem' }}>暂无分析数据</div>;
    }

    const timestampMatches = desc.split(/(\[\d{2}:\d{2}s\])/g).filter(Boolean);
    if (timestampMatches.length > 1) {
      const keyframes: { time: string; text: string }[] = [];
      for (let i = 0; i < timestampMatches.length; i++) {
        if (timestampMatches[i].startsWith('[') && timestampMatches[i].endsWith('s]')) {
          const time = timestampMatches[i];
          const text = timestampMatches[i + 1] ? timestampMatches[i + 1].trim() : '';
          keyframes.push({ time, text });
          i++;
        }
      }
      if (keyframes.length > 0) {
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {keyframes.map((kf, idx) => (
              <div key={idx} style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(6, 182, 212, 0.25)',
                borderRadius: 12, padding: '0.85rem 1rem',
                display: 'flex', flexDirection: 'column', gap: '0.4rem',
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{
                    background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
                    color: '#fff', fontSize: '0.72rem', fontWeight: 700,
                    padding: '0.2rem 0.55rem', borderRadius: 6, display: 'flex', alignItems: 'center', gap: '0.3rem'
                  }}>
                    <Clock size={12} /> {kf.time} 时序关键帧 #{idx + 1}
                  </span>
                </div>
                <div style={{ fontSize: '0.84rem', color: '#e5e7eb', lineHeight: 1.6 }}>
                  {kf.text}
                </div>
              </div>
            ))}
          </div>
        );
      }
    }

    const lines = desc.split(/\n+/).map(l => l.trim()).filter(Boolean);
    if (lines.length > 1) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          {lines.map((line, idx) => {
            let icon = <Sparkles size={15} color="#06b6d4" />;
            let borderColor = 'rgba(255, 255, 255, 0.08)';
            let titleTag = '';

            if (/主体|细节|人物|对象/i.test(line)) {
              icon = <User size={15} color="#6366f1" />;
              borderColor = 'rgba(99, 102, 241, 0.3)';
              titleTag = '主体与细节';
            } else if (/场景|空间|构图|背景/i.test(line)) {
              icon = <Mountain size={15} color="#10b981" />;
              borderColor = 'rgba(16, 185, 129, 0.3)';
              titleTag = '场景与构图';
            } else if (/色彩|光影|基调|色调/i.test(line)) {
              icon = <Palette size={15} color="#ec4899" />;
              borderColor = 'rgba(236, 72, 153, 0.3)';
              titleTag = '色彩与光影';
            } else if (/情绪|氛围|艺术|风格/i.test(line)) {
              icon = <Heart size={15} color="#f59e0b" />;
              borderColor = 'rgba(245, 158, 11, 0.3)';
              titleTag = '情绪与风格';
            } else if (/ASR|语音|对白|转写/i.test(line)) {
              icon = <Radio size={15} color="#06b6d4" />;
              borderColor = 'rgba(6, 182, 212, 0.3)';
              titleTag = '语音与对白';
            } else if (/文字|印花|商标|OCR/i.test(line)) {
              icon = <Type size={15} color="#3b82f6" />;
              borderColor = 'rgba(59, 130, 246, 0.3)';
              titleTag = '文字与标识';
            }

            return (
              <div key={idx} style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: `1px solid ${borderColor}`,
                borderRadius: 12, padding: '0.75rem 0.95rem',
                display: 'flex', flexDirection: 'column', gap: '0.35rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  {icon}
                  {titleTag ? (
                    <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#e5e7eb' }}>
                      {titleTag}
                    </span>
                  ) : null}
                </div>
                <div style={{ fontSize: '0.84rem', color: '#e5e7eb', lineHeight: 1.6 }}>
                  {line}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    return (
      <div style={{
        background: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid rgba(6, 182, 212, 0.2)',
        borderRadius: 12, padding: '1rem',
        fontSize: '0.86rem', color: '#e5e7eb', lineHeight: 1.7
      }}>
        {desc}
      </div>
    );
  };

  const radarData = [
    { subject: 'RGB视觉/关键帧', thumbnail: indexResult ? 85 : 0, content: indexResult ? 60 : 0 },
    { subject: 'VLM语义描述', thumbnail: indexResult ? 40 : 0, content: indexResult ? 95 : 0 },
    { subject: 'CLAP声学特征', thumbnail: indexResult ? 30 : 0, content: indexResult ? 80 : 0 },
    { subject: '6维结构标签', thumbnail: indexResult ? 55 : 0, content: indexResult ? 90 : 0 },
    { subject: '空间运镜构图', thumbnail: indexResult ? 88 : 0, content: indexResult ? 70 : 0 },
    { subject: 'ASR语音文本', thumbnail: indexResult ? 20 : 0, content: indexResult ? 85 : 0 },
  ];

  const getMethodBadgeStyle = (method: string) => {
    switch (method) {
      case 'POST': return { background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.4)' };
      case 'GET': return { background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.4)' };
      case 'DELETE': return { background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)' };
      case 'WS': return { background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.4)' };
      default: return { background: 'rgba(255, 255, 255, 0.1)', color: '#fff' };
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      
      {/* Top Header Navigation */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(9, 11, 16, 0.85)', backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '0.85rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: 'linear-gradient(135deg, #6366f1 0%, #ec4899 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.4)'
            }}>
              <Brain size={22} color="#fff" />
            </div>
            <div>
              <div style={{
                fontFamily: 'Outfit, sans-serif', fontWeight: 800, fontSize: '1.2rem',
                background: 'linear-gradient(135deg, #6366f1 0%, #ec4899 100%)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
              }}>
                Antigravity 多模态推荐与检索系统
              </div>
              <div style={{ fontSize: '0.72rem', color: '#9ca3af' }}>
                Qwen3-VL-8B + Qwen3-VL-Embedding + Whisper + CLAP
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav style={{ display: 'flex', gap: '0.4rem', background: 'rgba(255,255,255,0.04)', padding: '0.25rem', borderRadius: 10 }}>
            {[
              { id: 'studio', label: '工作台 (Studio)', icon: <Sparkles size={14} /> },
              { id: 'search', label: '多模态检索中心', icon: <Search size={14} /> },
              { id: 'lab', label: '向量与模型实验室', icon: <Terminal size={14} /> },
              { id: 'library', label: '索引库与监控', icon: <Database size={14} /> },
              { id: 'docs', label: '开发者接口中心 (API Docs)', icon: <BookOpen size={14} /> },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                style={{
                  border: 'none',
                  background: activeTab === tab.id ? 'linear-gradient(135deg, #6366f1 0%, #818cf8 100%)' : 'transparent',
                  color: activeTab === tab.id ? '#fff' : '#9ca3af',
                  padding: '0.45rem 0.85rem',
                  borderRadius: 8,
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  transition: 'all 0.2s ease'
                }}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Tenant Isolation Selector */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.45rem',
            background: 'rgba(99, 102, 241, 0.12)',
            border: '1px solid rgba(99, 102, 241, 0.35)',
            padding: '0.3rem 0.65rem', borderRadius: 10,
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
          }}>
            <Layers size={13} color="#818cf8" />
            <span style={{ fontSize: '0.74rem', color: '#c7d2fe', fontWeight: 600 }}>租户空间:</span>
            <select
              value={activeTenant}
              onChange={(e) => {
                const newT = e.target.value;
                setActiveTenant(newT);
                fetchLibrary(newT);
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#fff',
                fontSize: '0.76rem',
                fontWeight: 700,
                cursor: 'pointer',
                outline: 'none',
                paddingRight: '0.2rem'
              }}
            >
              <option value="default" style={{ background: '#1e1e2f', color: '#fff' }}>default (全局空间)</option>
              <option value="tenant_alpha" style={{ background: '#1e1e2f', color: '#fff' }}>tenant_alpha (业务线 A)</option>
              <option value="tenant_beta" style={{ background: '#1e1e2f', color: '#fff' }}>tenant_beta (业务线 B)</option>
              <option value="workspace_corp" style={{ background: '#1e1e2f', color: '#fff' }}>workspace_corp (企业库)</option>
            </select>
          </div>

          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.45rem',
            background: wsConnected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
            border: `1px solid ${wsConnected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
            padding: '0.35rem 0.75rem', borderRadius: 20
          }}>
            <div className="animate-pulse-glow" style={{ width: 7, height: 7, borderRadius: '50%', background: wsConnected ? '#10b981' : '#f59e0b' }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: wsConnected ? '#10b981' : '#f59e0b' }}>
              {bootStatus}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '0.35rem 0.75rem', borderRadius: 20 }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#818cf8' }}>常驻显存: 12.0GB / 20.0GB OK</span>
          </div>
        </div>
      </header>

      {/* Main Content Area Based on Active Tab */}
      <main style={{ maxWidth: 1440, margin: '1.5rem auto', padding: '0 1.5rem', flex: 1, width: '100%' }}>

        {/* TAB 1: STUDIO */}
        {activeTab === 'studio' && (
          <div style={{ display: 'grid', gridTemplateColumns: '430px 1fr', gap: '1.75rem' }}>
            
            {/* Left Column: Upload & Dimension Config */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.1rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                    <CloudUpload size={19} color="#6366f1" /> 多模态文件上传与配置
                  </div>
                </div>

                {/* Dropzone */}
                <div style={{
                  border: '2px dashed rgba(99, 102, 241, 0.4)', borderRadius: 14, padding: '1.5rem 1rem', textAlign: 'center',
                  background: 'rgba(99, 102, 241, 0.04)', cursor: 'pointer', position: 'relative', marginBottom: '1.25rem'
                }}>
                  <input type="file" onChange={handleFileChange} accept="image/*,video/*,audio/*" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer' }} />
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                    <ImageIcon size={28} color="#ec4899" />
                    <Video size={28} color="#06b6d4" />
                    <Music size={28} color="#10b981" />
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.92rem', color: '#fff' }}>
                    {file ? file.name : '点击或拖拽上传 本地媒体文件'}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#9ca3af', marginTop: '0.3rem' }}>
                    支持图片 (.jpeg, .png) / 视频 (.mov, .mp4) / 音频 (.wav, .mp3)
                  </div>
                </div>

                {/* Execution Mode Selector */}
                <div style={{ marginBottom: '1.1rem' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#e5e7eb', marginBottom: '0.45rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Zap size={14} color="#f59e0b" /> 选择运行模式 (按需选择生成):
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.45rem' }}>
                    {[
                      { id: 'full', label: '🚀 全流程推荐', badge: '完整', desc: '快速索引+VLM+标签+推荐' },
                      { id: 'vlm_only', label: '🧠 大模型理解与标签', badge: 'VLM', desc: '仅深度解析与标签归类' },
                      { id: 'fast_vector', label: '⚡ 仅快速特征 (<50ms)', badge: '极速', desc: '仅提取基础向量与主色' },
                      { id: 'embedding_only', label: '🎯 仅 2048 维向量', badge: '2048d', desc: '仅生成稠密特征向量' },
                    ].map(m => (
                      <button
                        key={m.id}
                        onClick={() => setExecutionMode(m.id as any)}
                        style={{
                          border: executionMode === m.id ? '1px solid rgba(245, 158, 11, 0.7)' : '1px solid rgba(255, 255, 255, 0.08)',
                          background: executionMode === m.id ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          color: executionMode === m.id ? '#fcd34d' : '#9ca3af',
                          padding: '0.5rem 0.6rem', borderRadius: 10, textAlign: 'left', cursor: 'pointer',
                          transition: 'all 0.2s ease', display: 'flex', flexDirection: 'column', gap: '0.15rem'
                        }}
                      >
                        <div style={{ fontSize: '0.76rem', fontWeight: 700, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>{m.label}</span>
                          <span style={{ fontSize: '0.62rem', background: 'rgba(255,255,255,0.1)', padding: '0.1rem 0.3rem', borderRadius: 4 }}>{m.badge}</span>
                        </div>
                        <div style={{ fontSize: '0.65rem', color: '#6b7280' }}>{m.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Dynamic Analysis Dimension Selector (only shown when VLM is involved) */}
                {(executionMode === 'full' || executionMode === 'vlm_only') && (
                  <div style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '0.85rem 1rem', marginBottom: '1.1rem' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#e5e7eb', marginBottom: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Sliders size={14} color="#06b6d4" /> 自定义大模型分析重点维度:
                    </div>
                    
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}>
                      {dimensionOptions.map(opt => {
                        const isSelected = focusDimensions.includes(opt.key);
                        return (
                          <button
                            key={opt.key}
                            onClick={() => toggleDimension(opt.key)}
                            style={{
                              background: isSelected ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                              border: isSelected ? '1px solid rgba(99, 102, 241, 0.6)' : '1px solid rgba(255, 255, 255, 0.1)',
                              color: isSelected ? '#a5b4fc' : '#9ca3af',
                              padding: '0.3rem 0.55rem',
                              borderRadius: 8,
                              fontSize: '0.73rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              transition: 'all 0.2s ease'
                            }}
                          >
                            {opt.icon}
                            {opt.label}
                          </button>
                        );
                      })}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                      <div style={{ fontSize: '0.72rem', color: '#9ca3af' }}>🎯 补充关注指令 (可选):</div>
                      <input
                        type="text"
                        placeholder="如: '重点分析服饰颜色与面料发型', '分析商品成色细节'..."
                        value={customPrompt}
                        onChange={e => setCustomPrompt(e.target.value)}
                        style={{
                          background: 'rgba(255, 255, 255, 0.04)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          borderRadius: 8,
                          padding: '0.5rem 0.75rem',
                          color: '#fff',
                          fontSize: '0.75rem',
                          outline: 'none'
                        }}
                      />
                    </div>
                  </div>
                )}

                <button onClick={handleUpload} disabled={isUploading || !file} style={{
                  background: !file ? 'rgba(255,255,255,0.08)' : 'linear-gradient(135deg, #6366f1 0%, #ec4899 100%)',
                  border: 'none', color: !file ? '#6b7280' : '#fff', padding: '0.85rem 1.5rem',
                  borderRadius: 12, fontWeight: 600, cursor: !file ? 'not-allowed' : 'pointer', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem'
                }}>
                  <Zap size={18} /> {isUploading ? '正在执行自定义多模态推演...' : '触发 3 级渐进式向量索引'}
                </button>

                {progress > 0 && (
                  <div style={{ marginTop: '1.25rem' }}>
                    <div style={{ height: 8, background: 'rgba(255,255,255,0.1)', borderRadius: 4, overflow: 'hidden', marginBottom: '0.5rem' }}>
                      <div style={{ height: '100%', width: `${progress}%`, background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)', transition: 'width 0.4s ease' }} />
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#9ca3af', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{stageText}</span>
                      <span>{progress}%</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Model Status Card */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                    <Cpu size={20} color="#10b981" /> 多模态模型矩阵与显存常驻
                  </div>
                  <span style={{ fontSize: '0.75rem', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', padding: '0.2rem 0.5rem', borderRadius: 6, fontWeight: 600 }}>
                    12.0GB / 20.0GB
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {modelsList.map((m, i) => (
                    <div key={i} style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 10, padding: '0.65rem 0.8rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Disc size={13} color="#6366f1" /> {m.model_id.split('/').pop()}
                        </div>
                        <span style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem', borderRadius: 4, background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc', fontWeight: 600 }}>
                          {m.modality}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#9ca3af' }}>
                        <span>显存: <strong style={{ color: '#06b6d4' }}>{m.memory_gb} GB</strong></span>
                        <span style={{ color: '#10b981', fontWeight: 600 }}>● {m.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Radar Card */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                    <Layers size={20} color="#ec4899" /> 2048d 双轨向量空间雷达
                  </div>
                </div>
                <div style={{ height: 190, width: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                      <PolarGrid stroke="rgba(255,255,255,0.1)" />
                      <PolarAngleAxis dataKey="subject" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="transparent" />
                      <Radar name="视觉/声学特征" dataKey="thumbnail" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
                      <Radar name="VLM语义向量" dataKey="content" stroke="#ec4899" fill="#ec4899" fillOpacity={0.25} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>

            {/* Right Column: Dynamic VLM Analysis & Recommendations */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                    <Sparkles size={20} color="#06b6d4" /> 真实多模态媒体内容与特征解析
                  </div>
                  {indexResult && (
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span style={{ background: 'rgba(99, 102, 241, 0.2)', border: '1px solid rgba(99, 102, 241, 0.4)', color: '#a5b4fc', fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, fontWeight: 600 }}>
                        模态: {indexResult.media_type.toUpperCase()}
                      </span>
                      <button
                        onClick={handleCopyDescription}
                        style={{
                          background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: '#e5e7eb', fontSize: '0.72rem', padding: '0.25rem 0.6rem', borderRadius: 6,
                          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem'
                        }}
                      >
                        {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                        {copied ? '已复制' : '复制描述'}
                      </button>
                    </div>
                  )}
                </div>

                {!indexResult && !previewUrl ? (
                  <div style={{ textAlign: 'center', padding: '3.5rem 1rem', color: '#6b7280' }}>
                    <UploadCloud size={54} color="rgba(255,255,255,0.15)" style={{ margin: '0 auto 1rem auto' }} />
                    <div style={{ fontSize: '1rem', color: '#9ca3af', fontWeight: 600 }}>暂无多模态分析结果</div>
                    <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.4rem' }}>
                      请在左侧上传图片、视频或音频文件，选择分析维度后点击“触发 3 级渐进式向量索引”
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem' }}>
                      <div>
                        <div style={{ width: '100%', height: 230, borderRadius: 12, overflow: 'hidden', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.85rem' }}>
                          {previewUrl ? (
                            activeMediaType === 'video' ? (
                              <video src={previewUrl} controls autoPlay muted playsInline style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                            ) : activeMediaType === 'audio' ? (
                              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', width: '90%' }}>
                                <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(16, 185, 129, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <Music size={28} color="#10b981" />
                                </div>
                                <audio src={previewUrl} controls autoPlay style={{ width: '100%' }} />
                              </div>
                            ) : (
                              <img src={previewUrl} alt="Preview" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                            )
                          ) : (
                            <ImageIcon size={48} color="rgba(255,255,255,0.2)" />
                          )}
                        </div>

                        <div style={{ background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: 10, padding: '0.65rem 0.85rem' }}>
                          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#a5b4fc', marginBottom: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <Brain size={14} color="#6366f1" /> 核心多模态模型引擎:
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', fontSize: '0.72rem', color: '#9ca3af' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span>视觉感知:</span>
                              <strong style={{ color: '#06b6d4' }}>Qwen3-VL-8B (5.4GB GPU)</strong>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span>稠密向量:</span>
                              <strong style={{ color: '#10b981' }}>Qwen3-VL-Embedding (2048d)</strong>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span>音频特征:</span>
                              <strong style={{ color: '#ec4899' }}>Whisper-v3 + CLAP (512d)</strong>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#06b6d4', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <Sparkles size={16} /> 大模型多维深度特征理解与结构化语义
                          </div>
                          <span style={{ fontSize: '0.72rem', color: '#10b981', background: 'rgba(16, 185, 129, 0.15)', padding: '0.15rem 0.45rem', borderRadius: 4, fontWeight: 600 }}>
                            2048d 向量对齐
                          </span>
                        </div>

                        <div style={{
                          background: 'rgba(0, 0, 0, 0.35)', border: '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: 12, padding: '1rem', maxHeight: 260, overflowY: 'auto'
                        }}>
                          {renderStructuredDescription()}
                        </div>
                      </div>
                    </div>

                    {indexResult?.categorized_tags && (
                      <div style={{ marginTop: '1.5rem' }}>
                        <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Tags size={18} color="#f59e0b" /> 6 大维度体系结构化分类标签 (Categorized Tags)
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 12, padding: '0.85rem 1rem' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <User size={14} color="#6366f1" /> Subject (主体)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {(indexResult.categorized_tags.Subject || ['媒体主体']).map((t, i) => (
                                <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc', border: '1px solid rgba(99, 102, 241, 0.3)' }}>{t}</span>
                              ))}
                            </div>
                          </div>

                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 12, padding: '0.85rem 1rem' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Palette size={14} color="#ec4899" /> ColorStyle (色彩风格)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {(indexResult.categorized_tags.ColorStyle || ['自然风格']).map((t, i) => (
                                <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, background: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.3)' }}>{t}</span>
                              ))}
                            </div>
                          </div>

                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 12, padding: '0.85rem 1rem' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Mountain size={14} color="#10b981" /> Scene (场景)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {(indexResult.categorized_tags.Scene || ['应用场景']).map((t, i) => (
                                <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, background: 'rgba(168, 85, 247, 0.15)', color: '#6ee7b7', border: '1px solid rgba(16, 185, 129, 0.3)' }}>{t}</span>
                              ))}
                            </div>
                          </div>

                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 12, padding: '0.85rem 1rem' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Heart size={14} color="#f59e0b" /> Emotion (情绪氛围)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {(indexResult.categorized_tags.Emotion || ['自然氛围']).map((t, i) => (
                                <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, background: 'rgba(245, 158, 11, 0.15)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)' }}>{t}</span>
                              ))}
                            </div>
                          </div>

                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 12, padding: '0.85rem 1rem' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Crop size={14} color="#06b6d4" /> Composition (空间构图)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {(indexResult.categorized_tags.Composition || ['标准构图']).map((t, i) => (
                                <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, background: 'rgba(6, 182, 212, 0.15)', color: '#67e8f9', border: '1px solid rgba(6, 182, 212, 0.3)' }}>{t}</span>
                              ))}
                            </div>
                          </div>

                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: 12, padding: '0.85rem 1rem' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Boxes size={14} color="#a855f7" /> Entity (实体对象)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {(indexResult.categorized_tags.Entity || [indexResult.title]).map((t, i) => (
                                <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6, background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)' }}>{t}</span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

              </div>

              {/* Item-to-Item Recommendations Card */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                    <Layers size={20} color="#10b981" /> Item-to-Item 智能关联推荐
                  </div>
                </div>

                {recommendations.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '1.75rem 1rem', color: '#6b7280', fontSize: '0.82rem' }}>
                    <Info size={18} color="rgba(255,255,255,0.2)" style={{ margin: '0 auto 0.4rem auto' }} />
                    暂无推荐结果，上传文件或索引后将自动生成基于深度双轨向量的相似推荐
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '1rem' }}>
                    {recommendations.map((rec, idx) => (
                      <div key={idx} style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: 12, padding: '1rem', position: 'relative' }}>
                        <div style={{ position: 'absolute', top: 10, right: 10, background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)', color: '#fff', fontWeight: 700, fontSize: '0.72rem', padding: '0.2rem 0.55rem', borderRadius: 10 }}>
                          {(rec.score * 100).toFixed(1)}%
                        </div>
                        <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#fff', marginBottom: '0.3rem', paddingRight: '4rem' }}>{rec.title}</div>
                        <div style={{ fontSize: '0.7rem', color: '#06b6d4', marginBottom: '0.4rem' }}>{rec.media_type.toUpperCase()} • {rec.item_id}</div>
                        <div style={{ fontSize: '0.76rem', color: '#9ca3af', lineHeight: 1.4, background: 'rgba(0,0,0,0.25)', padding: '0.5rem', borderRadius: 6 }}>
                          {rec.explanation}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>

          </div>
        )}

        {/* TAB 2: SEARCH HUB */}
        {activeTab === 'search' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="glass-panel">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                  <Search size={22} color="#06b6d4" /> 跨模态多路召回与融合排序检索中心 (RRF + Rerank)
                </div>

                <div style={{ display: 'flex', gap: '0.35rem', background: 'rgba(255,255,255,0.05)', padding: '0.2rem', borderRadius: 8 }}>
                  {['all', 'image', 'video', 'audio'].map((f) => (
                    <button
                      key={f}
                      onClick={() => setSearchFilter(f)}
                      style={{
                        border: 'none',
                        background: searchFilter === f ? 'rgba(99, 102, 241, 0.4)' : 'transparent',
                        color: searchFilter === f ? '#fff' : '#9ca3af',
                        padding: '0.3rem 0.75rem',
                        borderRadius: 6,
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      {f === 'all' ? '全模态 (All)' : (f === 'image' ? '🖼️ 图片' : (f === 'video' ? '🎬 视频' : '🎵 音频'))}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <input
                  type="text"
                  placeholder="输入任意自然语言语义描述 (例如: '粉色上衣自拍 车内后视镜', '开壳鲜活生蚝 柠檬冷色调', '环境人声音轨')..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, padding: '0.9rem 1.25rem', color: '#fff', fontSize: '0.95rem', outline: 'none' }}
                />
                <button onClick={handleSearch} disabled={isSearching} style={{ background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)', border: 'none', color: '#fff', padding: '0 1.75rem', borderRadius: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.92rem' }}>
                  <Search size={18} /> {isSearching ? '检索中...' : '多模态联合检索'}
                </button>
              </div>

              {searchResults.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '4rem 1rem', color: '#6b7280' }}>
                  <Search size={48} color="rgba(255,255,255,0.15)" style={{ margin: '0 auto 1rem auto' }} />
                  <div style={{ fontSize: '1rem', color: '#9ca3af', fontWeight: 600 }}>输入关键词开始跨模态向量检索</div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.4rem' }}>
                    系统将通过 Qwen3-VL-Embedding (2048d) 在密集语义空间中执行余弦匹配与 Qwen3 重排
                  </div>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
                  {searchResults.map((res, idx) => (
                    <div key={idx} style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: 14, padding: '1.2rem', position: 'relative' }}>
                      <div style={{ position: 'absolute', top: 12, right: 12, background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)', color: '#fff', fontWeight: 700, fontSize: '0.78rem', padding: '0.25rem 0.65rem', borderRadius: 12 }}>
                        匹配度 {(res.score * 100).toFixed(1)}%
                      </div>
                      <div style={{ fontWeight: 700, fontSize: '0.96rem', color: '#fff', marginBottom: '0.4rem', paddingRight: '5rem' }}>{res.title}</div>
                      <div style={{ fontSize: '0.75rem', color: '#06b6d4', marginBottom: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span style={{ padding: '0.15rem 0.45rem', borderRadius: 4, background: 'rgba(6, 182, 212, 0.15)' }}>{res.media_type.toUpperCase()}</span>
                        <span>{res.item_id}</span>
                      </div>
                      <div style={{ fontSize: '0.82rem', color: '#d1d5db', lineHeight: 1.5, background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: 8 }}>
                        <Sparkles size={14} color="#f59e0b" style={{ display: 'inline', marginRight: 5 }} />
                        {res.explanation}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: VECTOR & MODEL LAB */}
        {activeTab === 'lab' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.75rem' }}>
            
            {/* Vector Embedding Generator */}
            <div className="glass-panel">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                  <Layers size={20} color="#6366f1" /> 2048 维稠密向量生成测试 (Qwen3-VL-Embedding)
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <textarea
                  rows={4}
                  placeholder="输入任意文本，点击生成 2048 维向量嵌入..."
                  value={labText}
                  onChange={e => setLabText(e.target.value)}
                  style={{
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 10, padding: '0.85rem', color: '#fff', fontSize: '0.85rem', outline: 'none'
                  }}
                />

                <button
                  onClick={handleGenerateEmbedding}
                  disabled={isEmbeddingLoading || !labText.trim()}
                  style={{
                    background: 'linear-gradient(135deg, #6366f1 0%, #818cf8 100%)',
                    border: 'none', color: '#fff', padding: '0.75rem', borderRadius: 10,
                    fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem'
                  }}
                >
                  <Zap size={16} /> {isEmbeddingLoading ? '计算中...' : '生成 2048 维稠密向量'}
                </button>

                {labVector && (
                  <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, padding: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.82rem' }}>
                      <span style={{ color: '#10b981', fontWeight: 600 }}>✅ 向量维度: {labDim} 维 (MRL Dense)</span>
                      <span style={{ color: '#9ca3af' }}>L2-Norm: 1.000</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#a5b4fc', fontFamily: 'monospace', wordBreak: 'break-all', maxHeight: 150, overflowY: 'auto' }}>
                      [{labVector.slice(0, 32).map(n => n.toFixed(6)).join(', ')}, ... ({labDim - 32} more)]
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Direct VLM Prompt Testing */}
            <div className="glass-panel">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                  <Terminal size={20} color="#ec4899" /> 直调大模型分析接口 (POST /api/v1/analyze)
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.3rem' }}>当前测试文件:</div>
                  <div style={{ fontSize: '0.82rem', color: '#fff', background: 'rgba(255,255,255,0.05)', padding: '0.5rem 0.75rem', borderRadius: 8 }}>
                    {file ? file.name : '（请在工作台选择文件，或默认使用 test_files/beauty_1755438760705.jpeg）'}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.3rem' }}>自定义关注指令:</div>
                  <textarea
                    rows={3}
                    value={labPrompt}
                    onChange={e => setLabPrompt(e.target.value)}
                    style={{
                      width: '100%', background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: 10,
                      padding: '0.85rem', color: '#fff', fontSize: '0.85rem', outline: 'none'
                    }}
                  />
                </div>

                <button
                  onClick={handleDirectAnalyze}
                  disabled={isLabAnalyzing}
                  style={{
                    background: 'linear-gradient(135deg, #ec4899 0%, #f472b6 100%)',
                    border: 'none', color: '#fff', padding: '0.75rem', borderRadius: 10,
                    fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem'
                  }}
                >
                  <Play size={16} /> {isLabAnalyzing ? 'GPU 推演中...' : '发送请求至 Qwen3-VL-8B'}
                </button>

                {labResult && (
                  <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, padding: '1rem', maxHeight: 200, overflowY: 'auto' }}>
                    <div style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700, marginBottom: '0.4rem' }}>
                      Status: {labResult.status} | 嵌入维度: {labResult.embedding_dim}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#e5e7eb', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                      {labResult.description}
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

        {/* TAB 4: LIBRARY & MONITOR */}
        {activeTab === 'library' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="glass-panel">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#fff' }}>
                  <Database size={20} color="#10b981" /> 已建立多模态索引条目库 ({libraryItems.length} 项)
                </div>
                <button
                  onClick={() => fetchLibrary(activeTenant)}
                  style={{
                    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
                    color: '#fff', padding: '0.35rem 0.8rem', borderRadius: 8, fontSize: '0.75rem',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem'
                  }}
                >
                  <RefreshCw size={12} /> 刷新索引列表
                </button>
              </div>

              {isLibraryLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#06b6d4' }}>加载中...</div>
              ) : libraryItems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
                  租户 [{activeTenant}] 下暂无索引数据，请在工作台上传文件建立索引
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {libraryItems.map((item, idx) => (
                    <div key={idx} style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      borderRadius: 12, padding: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                    }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', flex: 1, paddingRight: '1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: 4, background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc', fontWeight: 600 }}>
                            {item.media_type.toUpperCase()}
                          </span>
                          <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: 4, background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', fontWeight: 600, border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                            租户: {item.tenant_id || 'default'}
                          </span>
                          {item.is_vectorized !== false ? (
                            <span style={{ fontSize: '0.68rem', padding: '0.12rem 0.4rem', borderRadius: 4, background: 'rgba(6, 182, 212, 0.15)', color: '#22d3ee', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                              <Check size={11} /> 向量已就绪
                            </span>
                          ) : (
                            <span style={{ fontSize: '0.68rem', padding: '0.12rem 0.4rem', borderRadius: 4, background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', fontWeight: 600 }}>
                              ⏳ 待向量化
                            </span>
                          )}
                          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff' }}>
                            {item.title}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: '#6b7280' }}>({item.item_id})</span>
                        </div>
                        <div style={{ fontSize: '0.78rem', color: '#9ca3af', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                          {item.description || '暂无详细描述'}
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeleteItem(item.item_id)}
                        style={{
                          background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)',
                          color: '#f87171', padding: '0.45rem 0.75rem', borderRadius: 8, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem'
                        }}
                      >
                        <Trash2 size={13} /> 删除
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 5: DEVELOPER & API DOCS PORTAL */}
        {activeTab === 'docs' && (
          <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.75rem' }}>
            
            {/* Left Column: API List Menu */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="glass-panel" style={{ padding: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '0.6rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <Code2 size={18} color="#6366f1" /> API 接口列表 ({apiDefinitions.length})
                  </div>
                  <a
                    href="http://localhost:8000/docs"
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: '0.7rem', color: '#06b6d4', display: 'flex', alignItems: 'center', gap: '0.2rem',
                      textDecoration: 'none', background: 'rgba(6, 182, 212, 0.1)', padding: '0.2rem 0.45rem', borderRadius: 6
                    }}
                  >
                    Swagger <ExternalLink size={10} />
                  </a>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {apiDefinitions.map((api) => {
                    const isSelected = selectedApiEndpoint === api.id;
                    const badge = getMethodBadgeStyle(api.method);
                    return (
                      <button
                        key={api.id}
                        onClick={() => {
                          setSelectedApiEndpoint(api.id);
                          setDocTestResponse(null);
                        }}
                        style={{
                          border: isSelected ? '1px solid rgba(99, 102, 241, 0.6)' : '1px solid transparent',
                          background: isSelected ? 'rgba(99, 102, 241, 0.18)' : 'rgba(255, 255, 255, 0.02)',
                          color: isSelected ? '#fff' : '#9ca3af',
                          padding: '0.55rem 0.75rem',
                          borderRadius: 8,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          textAlign: 'left',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                          <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '0.1rem 0.35rem', borderRadius: 4, ...badge }}>
                            {api.method}
                          </span>
                          <span style={{ fontSize: '0.78rem', fontWeight: isSelected ? 700 : 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {api.path}
                          </span>
                        </div>
                        <ChevronRight size={14} color={isSelected ? '#a5b4fc' : '#4b5563'} />
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Base Info Box */}
              <div className="glass-panel" style={{ padding: '1rem', fontSize: '0.74rem', color: '#9ca3af', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ fontWeight: 700, color: '#fff' }}>🌐 Base URL</div>
                <code style={{ background: 'rgba(0,0,0,0.4)', padding: '0.4rem', borderRadius: 6, color: '#10b981', fontFamily: 'monospace' }}>
                  http://localhost:8000
                </code>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.3rem' }}>
                  <span>Interactive Docs:</span>
                  <a href="/docs" target="_blank" style={{ color: '#06b6d4', textDecoration: 'none' }}>/docs</a>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>ReDoc Specification:</span>
                  <a href="/redoc" target="_blank" style={{ color: '#06b6d4', textDecoration: 'none' }}>/redoc</a>
                </div>
              </div>
            </div>

            {/* Right Column: Detailed API Specification & Playground */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="glass-panel">
                
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem', paddingBottom: '0.9rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
                      <span style={{ fontSize: '0.78rem', fontWeight: 800, padding: '0.2rem 0.55rem', borderRadius: 6, ...getMethodBadgeStyle(currentEndpoint.method) }}>
                        {currentEndpoint.method}
                      </span>
                      <span style={{ fontFamily: 'monospace', fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                        {currentEndpoint.path}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.92rem', fontWeight: 600, color: '#a5b4fc', marginTop: '0.2rem' }}>
                      {currentEndpoint.title}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.3rem', lineHeight: 1.5 }}>
                      {currentEndpoint.description}
                    </div>
                  </div>

                  <button
                    onClick={() => handleRunDocTest(currentEndpoint)}
                    disabled={docTestLoading}
                    style={{
                      background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
                      border: 'none', color: '#fff', padding: '0.5rem 1rem', borderRadius: 8,
                      fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem'
                    }}
                  >
                    <Send size={13} /> {docTestLoading ? '执行中...' : '在线测试接口'}
                  </button>
                </div>

                {/* Parameters Table */}
                <div style={{ marginBottom: '1.5rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff', marginBottom: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Sliders size={15} color="#06b6d4" /> 请求参数列表 (Parameters)
                  </div>

                  {currentEndpoint.params.length === 0 ? (
                    <div style={{ fontSize: '0.78rem', color: '#6b7280', background: 'rgba(255,255,255,0.02)', padding: '0.75rem', borderRadius: 8 }}>
                      该接口无需额外 Query / Body 参数
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: 10 }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ background: 'rgba(255, 255, 255, 0.04)', color: '#9ca3af', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                            <th style={{ padding: '0.6rem 0.8rem' }}>参数名 (Field)</th>
                            <th style={{ padding: '0.6rem 0.8rem' }}>位置 (In)</th>
                            <th style={{ padding: '0.6rem 0.8rem' }}>类型 (Type)</th>
                            <th style={{ padding: '0.6rem 0.8rem' }}>必填</th>
                            <th style={{ padding: '0.6rem 0.8rem' }}>默认值</th>
                            <th style={{ padding: '0.6rem 0.8rem' }}>说明</th>
                          </tr>
                        </thead>
                        <tbody>
                          {currentEndpoint.params.map((p, idx) => (
                            <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#e5e7eb' }}>
                              <td style={{ padding: '0.6rem 0.8rem', fontFamily: 'monospace', color: '#a5b4fc', fontWeight: 600 }}>{p.name}</td>
                              <td style={{ padding: '0.6rem 0.8rem' }}><span style={{ background: 'rgba(255,255,255,0.06)', padding: '0.1rem 0.35rem', borderRadius: 4 }}>{p.in}</span></td>
                              <td style={{ padding: '0.6rem 0.8rem', color: '#06b6d4', fontFamily: 'monospace' }}>{p.type}</td>
                              <td style={{ padding: '0.6rem 0.8rem' }}>{p.req ? <span style={{ color: '#f87171', fontWeight: 700 }}>必填</span> : <span style={{ color: '#9ca3af' }}>可选</span>}</td>
                              <td style={{ padding: '0.6rem 0.8rem', color: '#9ca3af', fontFamily: 'monospace' }}>{p.def}</td>
                              <td style={{ padding: '0.6rem 0.8rem', color: '#d1d5db' }}>{p.desc}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* cURL Example */}
                <div style={{ marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Terminal size={15} color="#f59e0b" /> cURL 调用代码示例
                    </div>
                    <button
                      onClick={() => copyToClipboard(currentEndpoint.curlSample, currentEndpoint.id)}
                      style={{
                        background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
                        color: '#fff', padding: '0.2rem 0.55rem', borderRadius: 6, fontSize: '0.7rem',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem'
                      }}
                    >
                      {copiedCurl === currentEndpoint.id ? <CheckCircle2 size={12} color="#10b981" /> : <Copy size={12} />}
                      {copiedCurl === currentEndpoint.id ? '已复制' : '复制代码'}
                    </button>
                  </div>
                  <pre style={{
                    background: 'rgba(0, 0, 0, 0.45)', border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: 10, padding: '0.85rem 1rem', fontSize: '0.75rem', color: '#fcd34d',
                    overflowX: 'auto', fontFamily: 'monospace', lineHeight: 1.5, margin: 0
                  }}>
                    {currentEndpoint.curlSample}
                  </pre>
                </div>

                {/* Response Schema Example & Live Test Viewer */}
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <CheckCircle2 size={15} color="#10b981" /> {docTestResponse ? '在线测试返回结果 (Live Response)' : '标准响应示例 (Response Schema)'}
                  </div>
                  <pre style={{
                    background: 'rgba(0, 0, 0, 0.45)', border: `1px solid ${docTestResponse ? 'rgba(16, 185, 129, 0.4)' : 'rgba(255, 255, 255, 0.08)'}`,
                    borderRadius: 10, padding: '0.85rem 1rem', fontSize: '0.75rem', color: docTestResponse ? '#34d399' : '#9ca3af',
                    overflowX: 'auto', maxHeight: 280, fontFamily: 'monospace', lineHeight: 1.5, margin: 0
                  }}>
                    {docTestResponse ? JSON.stringify(docTestResponse, null, 2) : currentEndpoint.responseSample}
                  </pre>
                </div>

              </div>
            </div>

          </div>
        )}

      </main>
    </div>
  );
}

export default App;
