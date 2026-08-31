"""q661 Tapestry Analogy -- transfer a loom relation after adjacency rewires."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STUDIO,SOURCE,TARGET,THREAD,SHUTTLE,GRAPH,GOAL,BAD=7,10,5,12,9,14,6,13,15
LEVELS=[{"name":"Crossing Relation","seq":(4,)},{"name":"Shifted Shuttle","seq":(1,4)},{"name":"Rewired Edge","seq":(2,1,4)},{"name":"Surface Disguise","seq":(3,1,2,4)},{"name":"Graph Transfer","seq":(1,3,2,1,4)},{"name":"Tapestry Analogy","seq":(2,1,3,2,1,3,4)}]
def advance(s,a):
 source,target,graph,examples,mapped,locked=s;x=list(source);y=list(target)
 if a==1:x[0]=(x[0]+1+graph)%6;y[1]=(y[1]+2)%6
 elif a==2:x[1]=(x[1]+2+len(examples))%6;y[0]=(y[0]+1+graph)%6;graph=(graph+1)%4
 elif a==3:x=x[1:]+x[:1];y[0],y[2]=y[2],y[0];examples=examples+((tuple(x),tuple(y),graph),)
 elif a==4:mapped=((x[1]-x[0])%6,(y[2]-y[1])%6,graph,examples[-2:])
 elif a==5:locked=(mapped,tuple(x),tuple(y),graph,examples[-2:])
 return tuple(x),tuple(y),graph,examples,mapped,locked
for x in LEVELS:
 s=((0,2,4),(1,3,5),0,(),None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STUDIO;f[8:32,7:29]=SOURCE;f[8:32,35:57]=TARGET
  for side,vals in enumerate((g.source,g.target)):
   ox=9+side*28
   for i,v in enumerate(vals):f[12+i*6:17+i*6,ox:ox+16]=THREAD;f[13+i*6:16+i*6,ox+2:ox+4+v*2]=SHUTTLE if side else GRAPH
  for i,(_,_,z) in enumerate(g.examples[-3:]):x=8+i*15;f[38:44,x:x+11]=GRAPH;f[45:48,x:x+3+z*2]=THREAD
  if g.mapped:f[51:55,8:45]=TARGET
  if g.locked:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q661(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q661",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=(0,2,4);self.target=(1,3,5);self.graph=0;self.examples=();self.mapped=self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.source,self.target,self.graph,self.examples,self.mapped,self.locked=advance((self.source,self.target,self.graph,self.examples,self.mapped,self.locked),a)
  elif a==6:
   if (self.source,self.target,self.graph,self.examples,self.mapped,self.locked)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
