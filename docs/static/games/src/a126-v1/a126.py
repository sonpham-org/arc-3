"""a126 Relation Closure -- add shortcuts according to directed reachability."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GRAPH,LEFT,RIGHT,EDGE,SHORTCUT,SELECT,REACHABLE,MISSING,BAD=7,8,12,14,9,10,13,4,6,15
EDGES=((0,1),(1,2),(2,3),(3,4),(4,5),(0,3),(1,4),(2,5),(3,0),(4,1),(5,2),(5,0))
LEVELS=[
 {"name":"Add Link","seq":(1,)},{"name":"Select Link","seq":(2,)},
 {"name":"Change Region","seq":(3,1)},{"name":"Compute Reachability","seq":(1,2,3,4,2)},
 {"name":"Add Fewest Shortcuts","seq":(1,3,2,1,4,3,2)},{"name":"Relation Closure","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def closure(mask):
 reach=[[i==j for j in range(6)] for i in range(6)]
 for e,(u,v) in enumerate(EDGES):reach[u][v]|=bool((mask>>e)&1)
 for k in range(6):
  for i in range(6):
   for j in range(6):reach[i][j]|=reach[i][k] and reach[k][j]
 return reach
def advance(s,a):
 mask,cursor,region,reachable,missing,shortcuts,history,snapshot=s
 if a==1:mask^=1<<cursor;shortcuts=(shortcuts+1)%8;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%len(EDGES);history=(history+(2,))[-8:]
 elif a==3:region=(region+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  r=closure(mask);sources=range(region,3);targets=range(3,6);reachable=sum(int(r[i][j]) for i in sources for j in targets);missing=(3-region)*3-reachable;history=(history+(4,))[-8:]
 elif a==5:snapshot=(mask,cursor,region,reachable,missing,shortcuts,history)
 return mask,cursor,region,reachable,missing,shortcuts,history,snapshot
for q in LEVELS:
 s=(0b000000011111,0,0,9,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GRAPH;pts=((11,15),(11,31),(11,47),(52,15),(52,31),(52,47))
  for e,(u,v) in enumerate(EDGES):
   if (g.mask>>e)&1:
    x1,y1=pts[u];x2,y2=pts[v];f[min(y1,y2):max(y1+1,y2+1),min(x1,x2):max(x1+1,x2+1)]=SHORTCUT if e>=5 else EDGE
  for i,(x,y) in enumerate(pts):f[y-5:y+6,x-5:x+6]=LEFT if i<3 else RIGHT
  u,v=EDGES[g.cursor];x1,y1=pts[u];x2,y2=pts[v];f[min(y1,y2)-2:min(y1,y2),min(x1,x2):max(x1+1,x2+1)]=SELECT
  f[54:58,8:8+min(9,g.reachable)*5]=REACHABLE;f[7:10,8:8+g.missing*5]=MISSING
  if g.bad:f[1:4,18:46]=BAD
  return f
class A126(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a126",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.mask,self.cursor,self.region,self.reachable,self.missing,self.shortcuts,self.history,self.snapshot=(0b000000011111,0,0,9,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.mask,self.cursor,self.region,self.reachable,self.missing,self.shortcuts,self.history,self.snapshot=advance((self.mask,self.cursor,self.region,self.reachable,self.missing,self.shortcuts,self.history,self.snapshot),a)
  elif a==6:
   if (self.mask,self.cursor,self.region,self.reachable,self.missing,self.shortcuts,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
