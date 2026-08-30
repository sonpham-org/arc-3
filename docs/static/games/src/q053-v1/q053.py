"""q053 Bridge Loom -- weave a load-bearing route from selectable anchor threads."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,ANCHOR,THREAD,NEEDED,CURSOR,BAD=9,10,1,6,14,12,8
LEVELS=[
 {"name":"First Thread","anchors":[(0,1),(1,1)],"ops":[(0,1)],"need":[(0,1)]},
 {"name":"Two Spans","anchors":[(0,1),(1,0),(2,1)],"ops":[(0,1),(1,2),(0,2)],"need":[(0,1),(1,2)]},
 {"name":"Tension Fork","anchors":[(0,1),(1,0),(1,2),(2,1)],"ops":[(0,1),(1,3),(0,2),(2,3),(1,2)],"need":[(0,2),(2,3)]},
 {"name":"Crossing Rule","anchors":[(0,0),(0,2),(2,0),(2,2)],"ops":[(0,2),(2,3),(0,3),(1,2),(0,1),(1,3)],"need":[(0,2),(2,3)]},
 {"name":"Load Path","anchors":[(0,1),(1,0),(1,2),(2,0),(2,2),(3,1)],"ops":[(0,1),(1,3),(3,5),(0,2),(2,4),(4,5),(1,2),(3,4)],"need":[(0,2),(2,4),(4,5)]},
 {"name":"Bridge Loom","anchors":[(0,1),(1,0),(1,2),(2,1),(3,0),(3,2),(4,1)],"ops":[(0,1),(1,3),(0,2),(2,3),(3,4),(4,6),(3,5),(5,6),(1,2),(4,5)],"need":[(0,2),(2,3),(3,4),(4,6)]}]
def norm(e):return tuple(sorted(e))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def p(self,a):x,y=a;return 8+x*11,20+y*11
 def line(self,f,a,b,c):
  x0,y0=self.p(a);x1,y1=self.p(b);n=max(abs(x1-x0),abs(y1-y0),1)
  for i in range(n+1):x=round(x0+(x1-x0)*i/n);y=round(y0+(y1-y0)*i/n);f[y-1:y+2,x-1:x+2]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=WATER
  for e in g.built:self.line(f,g.anchors[e[0]],g.anchors[e[1]],THREAD)
  for a in g.anchors:x,y=self.p(a);f[y-3:y+4,x-3:x+4]=ANCHOR
  for i in range(len(g.ops)):f[3:6,5+i*5:9+i*5]=CURSOR if i==g.cursor else NEEDED
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q053(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.anchors=[];self.ops=[];self.need=self.built=set();self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q053",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.anchors=list(s["anchors"]);self.ops=list(map(norm,s["ops"]));self.need=set(map(norm,s["need"]));self.built=set();self.cursor=0;self.failed=False
 def connected(self):
  seen={0};changed=True
  while changed:
   changed=False
   for a,b in self.built:
    if a in seen and b not in seen:seen.add(b);changed=True
    if b in seen and a not in seen:seen.add(a);changed=True
  return len(self.anchors)-1 in seen
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==5:self.built.add(self.ops[self.cursor])
  elif a==6:
   if self.need<=self.built and self.connected():self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
