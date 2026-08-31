"""q601 Tapestry Grammar -- compose grouped shuttle messages while completion rewires adjacency."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,SHUTTLE,THREAD,GROUP,RELAY,REWIRE,GOAL,BAD=3,8,14,10,6,11,12,13,15
LEVELS=[
 {"name":"Thread Word","seq":(1,2,4)},{"name":"Loom Phrase","seq":(2,3,4,5)},
 {"name":"Grouped Shuttle","seq":(1,3,2,4,4)},{"name":"Rewired Relay","seq":(3,1,4,2,5,4)},
 {"name":"Topology Message","seq":(1,2,4,3,5,2,4)},
 {"name":"Tapestry Grammar","seq":(2,1,3,4,5,2,3,4,1,4)}]
def advance(s,a):
 stack,graph,pattern,history,locked=s;v=list(stack)
 if a in (1,2,3):v.append((a+graph)%6);pattern=(pattern+a)%5
 elif a==4:
  if len(v)<2:return None
  b=v.pop();c=v.pop();v.append((c+2*b+graph)%6)
 elif a==5:graph=(graph+1+int(pattern>=2))%4;pattern=0
 history=history+(a,)
 if a==5:locked=(tuple(v),graph,pattern)
 return tuple(v),graph,pattern,history,locked
for x in LEVELS:
 s=((),0,0,(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 t=advance(s,5);x["plan"]=x["seq"]+(5,);x["target"]=t
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOOM
  for i in range(6):x=8+i*8;f[8:28,x:x+5]=THREAD;f[12+(i%2)*7:18+(i%2)*7,x:x+7]=SHUTTLE
  for i,v in enumerate(g.stack[-6:]):x=8+i*8;f[33:40,x:x+6]=GROUP;f[41:44,x:x+2+v]=THREAD
  for i,a in enumerate(g.history[-7:]):f[47:51,8+i*7:13+i*7]=REWIRE if a==5 else RELAY
  f[54:58,8:8+g.graph*11+7]=REWIRE
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q601(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q601",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stack=();self.graph=self.pattern=0;self.history=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stack,self.graph,self.pattern,self.history,self.locked),a)
   if s is None:self.bad=True;self.lose()
   else:self.stack,self.graph,self.pattern,self.history,self.locked=s
  elif a==6:
   if (self.stack,self.graph,self.pattern,self.history,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
