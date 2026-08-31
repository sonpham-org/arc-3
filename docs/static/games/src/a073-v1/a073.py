"""a073 Four-Bar Door -- move a latch along a closed-chain manifold."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WORKSHOP,LINK_A,LINK_B,JOINT,LATCH,OBSTACLE,SOCKET,PATH,BAD=1,8,9,12,14,10,4,13,6,15
POSITIONS=((18,39),(21,32),(27,24),(35,19),(43,23),(47,32),(42,41),(32,45),(23,44))
LEVELS=[
 {"name":"Move Joint","seq":(1,)},{"name":"Reverse Joint","seq":(1,2)},
 {"name":"Change Pivot","seq":(3,1,1)},{"name":"Round Obstacle","seq":(1,1,3,1,4)},
 {"name":"Constrained Arc","seq":(3,1,2,1,1,4,1)},{"name":"Four Bar Door","seq":(1,3,1,1,2,4,1,3,1,4)},
]
def advance(s,a):
 phase,pivot,latch,path,carried,history,snapshot=s
 if a==1:phase=(phase+1+pivot)%len(POSITIONS);latch=POSITIONS[phase];path=(path+(latch,))[-7:];history=(history+(1,))[-8:]
 elif a==2:phase=(phase-1-pivot)%len(POSITIONS);latch=POSITIONS[phase];path=(path+(latch,))[-7:];history=(history+(2,))[-8:]
 elif a==3:pivot^=1;history=(history+(3,))[-8:]
 elif a==4:carried=(latch,pivot,tuple(path));history=(history+(4,))[-8:]
 elif a==5:snapshot=(phase,pivot,latch,path,carried,history)
 return phase,pivot,latch,path,carried,history,snapshot
for x in LEVELS:
 s=(0,0,POSITIONS[0],(),None,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WORKSHOP;anchors=((16,16),(48,16));lx,ly=g.latch
  for ax,ay,col in ((anchors[0][0],anchors[0][1],LINK_A),(anchors[1][0],anchors[1][1],LINK_B)):
   steps=20
   for i in range(steps+1):x=ax+(lx-ax)*i//steps;y=ay+(ly-ay)*i//steps;f[y:y+3,x:x+3]=col
  f[12:20,12:20]=JOINT;f[12:20,44:52]=JOINT;f[ly-3:ly+4,lx-3:lx+4]=LATCH
  f[28:40,27:38]=OBSTACLE;f[43:53,47:57]=SOCKET
  for x,y in g.path:f[y:y+2,x:x+2]=PATH
  if g.bad:f[1:4,18:46]=BAD
  return f
class A073(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a073",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase,self.pivot,self.latch,self.path,self.carried,self.history,self.snapshot=(0,0,POSITIONS[0],(),None,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phase,self.pivot,self.latch,self.path,self.carried,self.history,self.snapshot=advance((self.phase,self.pivot,self.latch,self.path,self.carried,self.history,self.snapshot),a)
  elif a==6:
   if (self.phase,self.pivot,self.latch,self.path,self.carried,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
