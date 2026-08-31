"""a048 Livelock Lights -- break a mirrored yielding policy while staying safe."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CORRIDOR,WALL,ROBOT_A,ROBOT_B,LIGHT,RULE,PROGRESS,MOTION,BAD=8,9,4,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Polite Step","seq":(1,)},{"name":"Spot The Loop","seq":(1,1)},
 {"name":"Override One","seq":(2,1,1)},{"name":"Phase Response","seq":(4,1,2,1)},
 {"name":"Asymmetric Pass","seq":(1,3,4,1,2,1)},{"name":"Livelock Lights","seq":(1,1,2,4,1,3,1,2,1)},
]
def advance(s,a):
 pa,pb,ra,rb,phase,progress,history,snapshot=s
 if a==1:
  gap=pb-pa
  if gap<=2 and ra==rb:pa=max(0,pa-1);pb=min(9,pb+1)
  else:
   pa=min(9,pa+1+(ra^phase));pb=max(0,pb-1-(rb^phase))
   if pa>=pb:pa,pb=pb,pa;progress=(progress+1)%6
  history=(history+(gap,))[-8:]
 elif a==2:ra^=1;history=(history+(12,))[-8:]
 elif a==3:rb^=1;history=(history+(13,))[-8:]
 elif a==4:phase^=1;history=(history+(14,))[-8:]
 elif a==5:snapshot=(pa,pb,ra,rb,phase,progress,history)
 return pa,pb,ra,rb,phase,progress,history,snapshot
for x in LEVELS:
 s=(1,8,0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[6:58,5:59]=WALL;f[24:40,6:58]=CORRIDOR
  for i in range(10):x=7+i*5;f[27:37,x:x+4]=LIGHT if (i+g.phase)%2 else CORRIDOR
  xa=7+g.pa*5;xb=7+g.pb*5;f[21:43,xa:xa+4]=ROBOT_A;f[21:43,xb:xb+4]=ROBOT_B
  f[10:16,10:23]=RULE if g.ra else ROBOT_A;f[10:16,41:54]=RULE if g.rb else ROBOT_B
  for i in range(g.progress):f[48:53,9+i*8:15+i*8]=PROGRESS
  for i,v in enumerate(g.history[-8:]):f[55:58,10+i*5:14+i*5]=MOTION if v<10 else RULE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A048(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a048",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pa,self.pb,self.ra,self.rb,self.phase,self.progress,self.history,self.snapshot=(1,8,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pa,self.pb,self.ra,self.rb,self.phase,self.progress,self.history,self.snapshot=advance((self.pa,self.pb,self.ra,self.rb,self.phase,self.progress,self.history,self.snapshot),a)
  elif a==6:
   if (self.pa,self.pb,self.ra,self.rb,self.phase,self.progress,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
