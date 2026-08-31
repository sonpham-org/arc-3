"""a074 Linkage Walker -- tune crank holes and phase for a cyclic gait."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SKY,GROUND,BODY,LEG_A,LEG_B,CRANK,FOOT,STABLE,BAD=2,8,9,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Choose Hole","seq":(1,)},{"name":"Phase Offset","seq":(2,)},
 {"name":"First Cycle","seq":(1,2,3)},{"name":"Stable Foot","seq":(1,3,2,3,4)},
 {"name":"Uneven Ground","seq":(1,2,3,4,3,1,3)},{"name":"Linkage Walker","seq":(1,3,2,3,4,1,3,2,4,3)},
]
def advance(s,a):
 holes,phases,body,terrain,stable,steps,history,snapshot=s;h=list(holes);p=list(phases)
 if a==1:h[0]=1+h[0]%3;history=(history+(1,))[-8:]
 elif a==2:p[1]=(p[1]+2)%8;history=(history+(2,))[-8:]
 elif a==3:
  p=[(p[i]+h[i])%8 for i in range(2)];contact=sum(int(x in (4,5,6)) for x in p);body=min(10,body+int(contact==1));stable=min(5,stable+1) if contact else 0;steps=(steps+contact)%8;history=(history+(3,))[-8:]
 elif a==4:terrain=(terrain+1)%4;h[1]=1+(h[1]+terrain)%3;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(h),tuple(p),body,terrain,stable,steps,history)
 return tuple(h),tuple(p),body,terrain,stable,steps,history,snapshot
for x in LEVELS:
 s=((1,2),(0,4),0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SKY
  for x in range(4,60):y=48+(x//9+g.terrain)%3;f[y:60,x:x+1]=GROUND
  bx=8+g.body*4;f[24:35,bx:bx+18]=BODY
  for i,col in enumerate((LEG_A,LEG_B)):
   hipx=bx+4+i*9;px=hipx+(g.phases[i]-4)*2;py=47-(g.phases[i]%3)
   for j in range(12):x=hipx+(px-hipx)*j//11;y=34+(py-34)*j//11;f[y:y+3,x:x+3]=col
   f[py:py+4,px-2:px+5]=FOOT;f[19:23,hipx:hipx+g.holes[i]*3]=CRANK
  for i in range(g.stable):f[54:58,8+i*8:14+i*8]=STABLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A074(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a074",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.holes,self.phases,self.body,self.terrain,self.stable,self.steps,self.history,self.snapshot=((1,2),(0,4),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.holes,self.phases,self.body,self.terrain,self.stable,self.steps,self.history,self.snapshot=advance((self.holes,self.phases,self.body,self.terrain,self.stable,self.steps,self.history,self.snapshot),a)
  elif a==6:
   if (self.holes,self.phases,self.body,self.terrain,self.stable,self.steps,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
