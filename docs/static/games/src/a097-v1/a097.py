"""a097 Standing Room -- place boundaries so nodes and antinodes align."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ROOM,WALL,WAVE,NODE,ANTINODE,RECEIVER,FRAGILE,PULSE,BAD=9,8,4,12,10,14,13,11,6,15
LEVELS=[
 {"name":"Move Left Wall","seq":(1,)},{"name":"Move Right Wall","seq":(2,)},
 {"name":"Send Pulse","seq":(1,3)},{"name":"Find Antinode","seq":(1,2,3,4,3)},
 {"name":"Protect Fragile","seq":(2,1,3,4,1,3,4)},{"name":"Standing Room","seq":(1,2,3,4,2,3,1,4,3,4)},
]
def advance(s,a):
 walls,phase,pattern,receivers,fragile,pulses,history,snapshot=s;w=list(walls)
 if a==1:w[0]=min(w[1]-3,w[0]+1);history=(history+(1,))[-8:]
 elif a==2:w[1]=max(w[0]+3,w[1]-1);history=(history+(2,))[-8:]
 elif a==3:
  phase^=1;length=w[1]-w[0];pattern=tuple((x*2+phase)%max(2,length) for x in range(8));pulses=(pulses+1)%7;history=(history+(3,))[-8:]
 elif a==4:
  receivers=tuple((x+walls[0]+phase)%4 for x in (2,4,6));fragile=(fragile+sum(int(v==0) for v in receivers))%6;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(w),phase,pattern,receivers,fragile,pulses,history)
 return tuple(w),phase,pattern,receivers,fragile,pulses,history,snapshot
for x in LEVELS:
 s=((1,11),0,(),(0,0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROOM;lx=7+g.walls[0]*4;rx=7+g.walls[1]*4;f[10:52,lx:lx+4]=WALL;f[10:52,rx:rx+4]=WALL
  for i,v in enumerate(g.pattern):x=lx+3+i*max(1,(rx-lx-5)//8);h=3+(v%5)*3;f[31-h:32+h,x:x+3]=NODE if v%2==0 else ANTINODE
  for i,v in enumerate(g.receivers):x=15+i*16;f[49:56,x:x+9]=RECEIVER;f[50:55,x+2:x+7]=ANTINODE if v>=2 else FRAGILE
  f[7:10,8:8+g.pulses*6]=PULSE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A097(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a097",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.walls,self.phase,self.pattern,self.receivers,self.fragile,self.pulses,self.history,self.snapshot=((1,11),0,(),(0,0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.walls,self.phase,self.pattern,self.receivers,self.fragile,self.pulses,self.history,self.snapshot=advance((self.walls,self.phase,self.pattern,self.receivers,self.fragile,self.pulses,self.history,self.snapshot),a)
  elif a==6:
   if (self.walls,self.phase,self.pattern,self.receivers,self.fragile,self.pulses,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
