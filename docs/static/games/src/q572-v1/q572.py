"""q572 Lockwater Counter -- shape a rival while barge identities exchange appearance and position."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,IDENTITY,RIVAL,HISTORY,GOAL,BAD=2,9,14,10,6,12,11,13,15
LEVELS=[
 {"name":"First Counter","seq":(1,)},{"name":"Water Treatment","seq":(2,1)},
 {"name":"Identity Swap","seq":(3,1,2)},{"name":"Appearance Decoy","seq":(1,4,2,3)},
 {"name":"Shape The Rival","seq":(2,3,1,4,2,1)},
 {"name":"Lockwater Counter","seq":(3,1,2,4,1,3,2,1,4)}]
def advance(s,a):
 identities,colors,levels,recent,rival,exploit=s;i=list(identities);c=list(colors);w=list(levels)
 if a in (1,2):recent=(recent+(a,))[-2:];w[a-1]=(w[a-1]+a+rival)%5;rival=(sum(recent)+sum(w))%3
 elif a==3:i[0],i[1]=i[1],i[0];w[0],w[1]=w[1],w[0]
 elif a==4:c[0],c[2]=c[2],c[0];rival=(rival+c[0])%3
 elif a==5:exploit=(tuple(i),tuple(c),tuple(w),recent,rival)
 return tuple(i),tuple(c),tuple(w),recent,rival,exploit
for x in LEVELS:
 s=((0,1,2),(0,1,2),(1,2,3),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CANAL
  for slot,(identity,color,level) in enumerate(zip(g.identities,g.colors,g.levels)):
   x=8+slot*17;f[9:31,x:x+13]=WATER;f[26-level*4:30,x+2:x+11]=BARGE;f[33+identity:36+identity,x:x+13]=IDENTITY if color%2 else HISTORY
  for j,a in enumerate(g.recent):f[43:48,9+j*20:23+j*20]=HISTORY;f[45:47,12+j*20:12+j*20+a*4]=BARGE
  f[52:57,8:8+g.rival*16+8]=RIVAL
  if g.exploit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q572(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q572",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.colors=(0,1,2);self.levels=(1,2,3);self.recent=();self.rival=0;self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.colors,self.levels,self.recent,self.rival,self.exploit=advance((self.identities,self.colors,self.levels,self.recent,self.rival,self.exploit),a)
  elif a==6:
   if (self.identities,self.colors,self.levels,self.recent,self.rival,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
