"""a054 Merge Meter -- sustain throughput with bounded lane fairness."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ROAD,LANE,LEFT,RIGHT,BUFFER,GATE,RECEIVER,FAIR,BAD=14,8,9,12,10,4,11,13,6,15
LEVELS=[
 {"name":"Admit Left","seq":(1,)},{"name":"Admit Right","seq":(1,2)},
 {"name":"Serve Buffer","seq":(1,2,3)},{"name":"Bounded Alternation","seq":(1,1,2,3,3)},
 {"name":"Keep Nonempty","seq":(2,1,3,4,2,3,1)},{"name":"Merge Meter","seq":(1,2,1,3,4,2,3,1,3,2)},
]
def advance(s,a):
 sources,buffer,phase,served,streak,history,snapshot=s;src=list(sources);buf=list(buffer)
 if a in (1,2):
  lane=a-1;color=(lane+phase)%2;src[lane]=(src[lane]+1)%5
  if len(buf)<5:buf.append(color)
  history=(history+(a,))[-8:]
 elif a==3:
  if buf:
   v=buf.pop(0);streak=streak+1 if served and served[-1]==v else 1;served=(served+(v,))[-7:]
  history=(history+(3,))[-8:]
 elif a==4:phase^=1;buf=buf[1:]+buf[:1] if buf else buf;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(src),tuple(buf),phase,served,streak,history)
 return tuple(src),tuple(buf),phase,served,streak,history,snapshot
for x in LEVELS:
 s=((0,0),(),0,(),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROAD;f[12:22,6:39]=LANE;f[40:50,6:39]=LANE;f[25:37,27:57]=BUFFER
  for i,col in enumerate((LEFT,RIGHT)):
   y=13+i*28
   for j in range(g.sources[i]):f[y:y+8,8+j*6:13+j*6]=col
  for i,v in enumerate(g.buffer):f[27:35,29+i*5:33+i*5]=LEFT if v==0 else RIGHT
  f[22:40,22:27]=GATE;f[25:37,52:58]=RECEIVER
  for i,v in enumerate(g.served):f[53:57,8+i*6:13+i*6]=LEFT if v==0 else RIGHT
  f[6:9,8:8+g.streak*5]=FAIR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A054(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a054",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sources,self.buffer,self.phase,self.served,self.streak,self.history,self.snapshot=((0,0),(),0,(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.sources,self.buffer,self.phase,self.served,self.streak,self.history,self.snapshot=advance((self.sources,self.buffer,self.phase,self.served,self.streak,self.history,self.snapshot),a)
  elif a==6:
   if (self.sources,self.buffer,self.phase,self.served,self.streak,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
