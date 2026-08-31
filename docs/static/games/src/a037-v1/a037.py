"""a037 Heap Orchard -- maintain a max-heap through repeated local swaps and harvests."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,TREE,FRUIT,VALUE,SELECT,HARVEST,GOAL,BAD=6,10,8,14,11,12,5,13,15
LEVELS=[{"name":"Parent Swap","seq":(1,)},{"name":"Select Child","seq":(2,1)},{"name":"First Harvest","seq":(3,1,2)},{"name":"Restore Heap","seq":(4,2,1,3)},{"name":"Repeated Maximum","seq":(2,3,1,4,2,1)},{"name":"Heap Orchard","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 heap,selected,harvests,history,active,program=s;h=list(heap);out=list(harvests)
 if a==1:
  child=min(active-1,selected*2+1)
  if child>0 and h[child]>h[selected]:h[child],h[selected]=h[selected],h[child]
 elif a==2:selected=(selected+1)%max(1,active)
 elif a==3:
  if active>0:out.append(h[0]);h[0]=h[active-1];active-=1;selected=0
  history=history+((tuple(h),active,tuple(out)),)
 elif a==4:
  for i in range(active//2-1,-1,-1):
   children=[j for j in (2*i+1,2*i+2) if j<active]
   if children:
    j=max(children,key=lambda k:h[k])
    if h[j]>h[i]:h[j],h[i]=h[i],h[j]
 elif a==5:program=(tuple(h),selected,tuple(out),history[-4:],active)
 return tuple(h),selected,tuple(out),history,active,program
for x in LEVELS:
 s=((3,7,5,2,6,4,1),0,(),(),7,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD;pts=[(28,7),(16,21),(40,21),(9,36),(23,36),(37,36),(51,36)]
  f[14:18,22:42]=TREE;f[28:32,12:52]=TREE
  for i,(x,y) in enumerate(pts):f[y:y+10,x:x+10]=SELECT if i==g.selected else FRUIT if i<g.active else ORCHARD;f[y+7:min(58,y+10),x+2:x+2+(g.heap[i] if i<len(g.heap) else 0)]=VALUE
  for i,v in enumerate(g.harvests[-4:]):f[49:54,8+i*12:17+i*12]=HARVEST
  if g.program:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A037(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a037",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.heap=(3,7,5,2,6,4,1);self.selected=0;self.harvests=self.history=();self.active=7;self.program=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.heap,self.selected,self.harvests,self.history,self.active,self.program=advance((self.heap,self.selected,self.harvests,self.history,self.active,self.program),a)
  elif a==6:
   if (self.heap,self.selected,self.harvests,self.history,self.active,self.program)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
