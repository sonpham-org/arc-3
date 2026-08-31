"""a131 Symmetry Breaker -- place one marker that induces a complete deterministic scan."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MACHINE,PART,MARKER,SCAN,PATH,VISITED,REPEAT,COMPLETE,BAD=13,8,12,14,10,9,4,6,11,15
LEVELS=[
 {"name":"Move Marker","seq":(1,)},{"name":"Rotate Scanner","seq":(2,)},
 {"name":"Reverse Traversal","seq":(3,1)},{"name":"Visit Every Part","seq":(1,2,3,4,2)},
 {"name":"Avoid Repeat","seq":(1,3,2,1,4,3,2)},{"name":"Symmetry Breaker","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 marker,scanner,direction,visited,repeats,history,snapshot=s
 if a==1:marker=(marker+1)%8;history=(history+(1,))[-8:]
 elif a==2:scanner=(scanner+1)%8;history=(history+(2,))[-8:]
 elif a==3:direction*=-1;history=(history+(3,))[-8:]
 elif a==4:
  order=[];p=scanner
  for k in range(10):order.append(p);p=(p+direction+(1 if p==marker else 0))%8
  visited=len(set(order));repeats=len(order)-visited;history=(history+(4,))[-8:]
 elif a==5:snapshot=(marker,scanner,direction,visited,repeats,history)
 return marker,scanner,direction,visited,repeats,history,snapshot
for q in LEVELS:
 s=(0,0,1,1,9,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MACHINE;pts=((31,9),(46,15),(53,31),(46,47),(31,54),(16,47),(9,31),(16,15))
  for i,(x,y) in enumerate(pts):f[y-4:y+5,x-4:x+5]=MARKER if i==g.marker else SCAN if i==g.scanner else PART
  for i in range(g.visited):x,y=pts[i];f[y-2:y+3,x-2:x+3]=VISITED
  f[54:58,8:8+min(8,g.visited)*5]=COMPLETE;f[7:10,8:8+min(8,g.repeats)*5]=REPEAT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A131(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a131",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.marker,self.scanner,self.direction,self.visited,self.repeats,self.history,self.snapshot=(0,0,1,1,9,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.marker,self.scanner,self.direction,self.visited,self.repeats,self.history,self.snapshot=advance((self.marker,self.scanner,self.direction,self.visited,self.repeats,self.history,self.snapshot),a)
  elif a==6:
   if (self.marker,self.scanner,self.direction,self.visited,self.repeats,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
