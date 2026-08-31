"""a175 Macro State -- act on slow aggregate modes instead of fast microstates."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,PARTICLE_A,PARTICLE_B,MODE_A,MODE_B,SAMPLE,TRANSITION,CURSOR,ERROR=12,8,10,14,7,13,11,4,9,6
BAD=15
LEVELS=[
 {"name":"Advance Microstate","seq":(1,)},{"name":"Choose Snapshot","seq":(2,)},
 {"name":"Act on Macrostate","seq":(3,1)},{"name":"Detect Slow Mode","seq":(1,2,3,4,2)},
 {"name":"Ignore Fast Cycle","seq":(1,3,2,1,4,3,2)},{"name":"Macro State","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 micro,macro,sample,actions,transitions,error,history,snapshot=s
 if a==1:micro=(micro+1)%12;macro=(macro+int(micro in (0,6)))%3;history=(history+(1,))[-8:]
 elif a==2:sample=(sample+1)%4;history=(history+(2,))[-8:]
 elif a==3:actions=(actions+1)%7;macro=(macro+sample)%3;history=(history+(3,))[-8:]
 elif a==4:transitions=int(micro in (0,6))+actions;error=int(sample==0 and micro%6!=0);history=(history+(4,))[-8:]
 elif a==5:snapshot=(micro,macro,sample,actions,transitions,error,history)
 return micro,macro,sample,actions,transitions,error,history,snapshot
for q in LEVELS:
 s=(0,0,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i in range(12):x=8+(i%4)*13;y=10+(i//4)*13;f[y:y+9,x:x+9]=PARTICLE_A if (i+g.micro)%2==0 else PARTICLE_B
  f[48:55,8:28]=MODE_A if g.macro%2==0 else MODE_B;f[48:55,31:51]=SAMPLE;f[54:58,8:8+g.transitions*5]=TRANSITION;f[7:10,8:8+g.error*12]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A175(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a175",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.micro,self.macro,self.sample,self.actions,self.transitions,self.error,self.history,self.snapshot=(0,0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.micro,self.macro,self.sample,self.actions,self.transitions,self.error,self.history,self.snapshot=advance((self.micro,self.macro,self.sample,self.actions,self.transitions,self.error,self.history,self.snapshot),a)
  elif a==6:
   if (self.micro,self.macro,self.sample,self.actions,self.transitions,self.error,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
